"""ISO 14230-3 (KWP2000) client — Keyword Protocol 2000 diagnostic services.

A thin, transport-neutral client mirroring :mod:`protocol.uds`. Each method builds
the request PDU (service id + parameters), sends it via a
:class:`~transport.base.Transport` (physically addressed to one ECU), and returns
the parsed positive-response payload. Negative responses raise
:class:`KwpNegativeResponseError`; response-pending (NRC 0x78) is awaited
transparently.

KWP2000 wire format mirrors UDS: request ``SID [params]`` -> positive response
``(SID+0x40) [params]`` or negative response ``7F <SID> <NRC>``. Unlike UDS,
KWP2000 has no "suppress positive response" bit; TesterPresent instead carries a
response-required byte (``0x01`` = respond, ``0x02`` = no response).

    from transport.socketcan import SocketCanTransport
    from protocol.kwp2000 import KWP2000Client, Session

    with SocketCanTransport("can0", ecu=0) as t:
        kwp = KWP2000Client(t)
        kwp.start_diagnostic_session(Session.EXTENDED)
        vin = kwp.read_data_by_common_identifier(0xF190)
        seed = kwp.security_access_request_seed(1)
        kwp.security_access_send_key(1, my_key_fn(seed))
"""
from __future__ import annotations

from enum import IntEnum

from transport.base import Transport

from .dtc import decode_dtc
from .nrc import NRC, RESPONSE_PENDING  # canonical 0x7F code table


# --------------------------------------------------------------------------- #
#  Service IDs (request SIDs). Positive response SID = request SID + 0x40.
# --------------------------------------------------------------------------- #
class Service(IntEnum):
    START_DIAGNOSTIC_SESSION = 0x10
    ECU_RESET = 0x11
    CLEAR_DIAGNOSTIC_INFORMATION = 0x14
    READ_STATUS_OF_DTC = 0x17
    READ_DTCS_BY_STATUS = 0x18
    READ_ECU_IDENTIFICATION = 0x1A
    STOP_DIAGNOSTIC_SESSION = 0x20
    READ_DATA_BY_LOCAL_IDENTIFIER = 0x21
    READ_DATA_BY_COMMON_IDENTIFIER = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    SECURITY_ACCESS = 0x27
    DYNAMICALLY_DEFINE_LOCAL_IDENTIFIER = 0x2C
    WRITE_DATA_BY_COMMON_IDENTIFIER = 0x2E
    INPUT_OUTPUT_CONTROL_BY_LOCAL_IDENTIFIER = 0x30
    START_ROUTINE_BY_LOCAL_IDENTIFIER = 0x31
    STOP_ROUTINE_BY_LOCAL_IDENTIFIER = 0x32
    REQUEST_ROUTINE_RESULTS_BY_LOCAL_IDENTIFIER = 0x33
    REQUEST_DOWNLOAD = 0x34
    REQUEST_UPLOAD = 0x35
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37
    WRITE_DATA_BY_LOCAL_IDENTIFIER = 0x3B
    TESTER_PRESENT = 0x3E


class Session(IntEnum):
    """KWP2000 diagnostic session ids (ISO 14230-3 StartDiagnosticSession)."""

    DEFAULT = 0x81               # standardDiagnosticMode (StandardSession)
    ECU_FLASH_REPROGRAMMING = 0x85  # ECUProgrammingSession
    ECU_DEVELOPMENT = 0x86       # developmentSession
    ADJUSTMENT = 0x83            # endOfLineSystemAdjustmentMode
    EXTENDED = 0x92              # extendedDiagnosticSession (programming/adjustment)
    PROGRAMMING = 0x85           # alias — ECU programming session
    STANDARD = 0x81             # alias — default/standard session


class ResetType(IntEnum):
    POWER_ON = 0x01              # powerOnReset
    NON_VOLATILE_RESET = 0x82


class RoutineResultType(IntEnum):
    START = 0x31
    STOP = 0x32
    REQUEST_RESULTS = 0x33


class TesterPresentResponse(IntEnum):
    RESPONSE_REQUIRED = 0x01
    NO_RESPONSE_REQUIRED = 0x02


# Negative Response Codes (0x7F) live in protocol/nrc.py — the canonical table
# (ISO 14229-1 + legacy KWP2000 block-transfer codes). NRC and RESPONSE_PENDING
# are imported above and re-used here so there is one source of truth.

# DTC status bit meanings (KWP2000 statusOfDTC byte, ISO 14230-3).
_STATUS_BITS = (
    "testFailed",
    "testFailedThisOperationCycle",
    "pendingDTC",
    "confirmedDTC",
    "testNotCompletedSinceLastClear",
    "testFailedSinceLastClear",
    "testNotCompletedThisOperationCycle",
    "warningIndicatorRequested",
)


class KwpError(Exception):
    """Base class for KWP2000-layer errors."""


class KwpTimeoutError(KwpError):
    """The ECU did not respond within the timeout."""


class UnexpectedResponseError(KwpError):
    """The response SID did not match the request."""


class KwpNegativeResponseError(KwpError):
    """The ECU returned ``7F <sid> <nrc>``."""

    def __init__(self, request_sid: int, nrc: int):
        self.request_sid = request_sid
        self.nrc = nrc
        self.nrc_name = NRC.get(nrc, "unknown")
        super().__init__(
            f"KWP2000 0x{request_sid:02X} negative response: "
            f"0x{nrc:02X} {self.nrc_name}"
        )


def decode_dtc_status(status: int) -> dict[str, bool]:
    """Decode a KWP2000 statusOfDTC byte into named flags (ISO 14230-3)."""
    return {name: bool(status & (1 << i)) for i, name in enumerate(_STATUS_BITS)}


class KWP2000Client:
    """ISO 14230-3 (KWP2000) client over one physically-addressed ECU."""

    def __init__(self, transport: Transport, *, timeout: float = 1.0,
                 p2_star: float = 5.0, max_pending: int = 10):
        self._t = transport
        self.timeout = timeout
        self.p2_star = p2_star
        self.max_pending = max_pending

    # -- core request/response ----------------------------------------------
    def _send(self, sid: int, data: bytes = b"", *, expect_response: bool = True) -> bytes:
        payload = bytes([sid]) + bytes(data)
        responses = self._t.request(payload, functional=False, timeout=self.timeout)
        if not expect_response:
            return b""
        resp = self._pick(responses)
        resp = self._await_final(resp, sid)
        self._check(resp, sid)
        return resp[1:]  # strip the response SID

    def _pick(self, responses: list) -> bytes:
        for r in responses:
            if r.data:
                return bytes(r.data)
        raise KwpTimeoutError("no response from ECU")

    def _await_final(self, resp: bytes, sid: int) -> bytes:
        # Loop while the ECU says "response pending" (7F <sid> 78).
        pending = 0
        while (
            len(resp) >= 3
            and resp[0] == 0x7F
            and resp[2] == RESPONSE_PENDING
        ):
            pending += 1
            if pending > self.max_pending:
                raise KwpTimeoutError("too many responsePending (0x78) replies")
            more = self._t.receive(timeout=self.p2_star)
            resp = self._pick(more)
        return resp

    def _check(self, resp: bytes, sid: int) -> None:
        if resp and resp[0] == 0x7F:
            nrc = resp[2] if len(resp) >= 3 else 0x10
            raise KwpNegativeResponseError(sid, nrc)
        if not resp or resp[0] != (sid + 0x40) & 0xFF:
            got = resp[0] if resp else None
            raise UnexpectedResponseError(
                f"expected response SID 0x{(sid + 0x40) & 0xFF:02X}, got "
                f"{'0x%02X' % got if got is not None else 'nothing'}"
            )

    # -- 0x10 StartDiagnosticSession ----------------------------------------
    def start_diagnostic_session(self, session: int = Session.DEFAULT,
                                 data: bytes = b"") -> bytes:
        """0x10 — enter a diagnostic session. Returns echoed session params."""
        return self._send(
            Service.START_DIAGNOSTIC_SESSION, bytes([session]) + bytes(data)
        )

    # -- 0x20 StopDiagnosticSession -----------------------------------------
    def stop_diagnostic_session(self) -> None:
        """0x20 — leave the current session and return to default."""
        self._send(Service.STOP_DIAGNOSTIC_SESSION)

    # -- 0x11 ECUReset -------------------------------------------------------
    def ecu_reset(self, reset_type: int = ResetType.POWER_ON) -> bytes:
        """0x11 — reset the ECU."""
        return self._send(Service.ECU_RESET, bytes([reset_type]))

    # -- 0x1A ReadEcuIdentification -----------------------------------------
    def read_ecu_identification(self, option: int) -> bytes:
        """0x1A — read an ECU identification record. Strips the echoed option."""
        data = self._send(Service.READ_ECU_IDENTIFICATION, bytes([option]))
        return data[1:] if data else b""

    # -- 0x14 ClearDiagnosticInformation ------------------------------------
    def clear_diagnostic_information(self, group: int = 0xFF00) -> None:
        """0x14 — clear DTCs for a group (default 0xFF00 = all groups)."""
        self._send(
            Service.CLEAR_DIAGNOSTIC_INFORMATION,
            bytes([(group >> 8) & 0xFF, group & 0xFF]),
        )

    # -- 0x18 ReadDTCsByStatus ----------------------------------------------
    def read_dtcs_by_status(self, status: int = 0x00, group: int = 0xFF00) -> list[dict]:
        """0x18 — read DTCs matching a status of DTC / group of DTC.

        Request:  ``18 <statusOfDTC> <groupHigh> <groupLow>``.
        Response: ``58 <count> N*(DTChigh DTClow statusOfDTC)``.
        Returns ``[{code, status, flags}]``.
        """
        data = self._send(
            Service.READ_DTCS_BY_STATUS,
            bytes([status, (group >> 8) & 0xFF, group & 0xFF]),
        )
        # data = numberOfDTC(1) + N*(DTC[2] + statusOfDTC[1])
        records = data[1:]
        out: list[dict] = []
        for i in range(0, len(records) - (len(records) % 3), 3):
            hi, lo, st = records[i], records[i + 1], records[i + 2]
            out.append({
                "code": decode_dtc(hi, lo),
                "status": st,
                "flags": decode_dtc_status(st),
            })
        return out

    # -- 0x17 ReadStatusOfDTC -----------------------------------------------
    def read_status_of_dtc(self, dtc: int) -> list[dict]:
        """0x17 — read the status of a specific DTC (or 0xFF00 style group)."""
        data = self._send(
            Service.READ_STATUS_OF_DTC, bytes([(dtc >> 8) & 0xFF, dtc & 0xFF])
        )
        # Response = SID + N*(DTChigh DTClow statusOfDTC); no leading count byte.
        records = data
        out: list[dict] = []
        for i in range(0, len(records) - (len(records) % 3), 3):
            hi, lo, st = records[i], records[i + 1], records[i + 2]
            out.append({
                "code": decode_dtc(hi, lo),
                "status": st,
                "flags": decode_dtc_status(st),
            })
        return out

    # -- 0x21 ReadDataByLocalIdentifier -------------------------------------
    def read_data_by_local_identifier(self, lid: int) -> bytes:
        """0x21 — read a record by local identifier. Strips the echoed LID."""
        data = self._send(Service.READ_DATA_BY_LOCAL_IDENTIFIER, bytes([lid & 0xFF]))
        return data[1:] if data else b""

    # -- 0x22 ReadDataByCommonIdentifier ------------------------------------
    def read_data_by_common_identifier(self, did: int) -> bytes:
        """0x22 — read a record by common (2-byte) identifier. Strips echoed DID."""
        data = self._send(
            Service.READ_DATA_BY_COMMON_IDENTIFIER,
            bytes([(did >> 8) & 0xFF, did & 0xFF]),
        )
        return data[2:] if len(data) >= 2 else b""

    # -- 0x23 ReadMemoryByAddress -------------------------------------------
    def read_memory_by_address(self, address: int, size: int,
                               *, addr_bytes: int = 3, size_bytes: int = 1) -> bytes:
        """0x23 — read raw memory. KWP2000 uses a 3-byte address + 1-byte size."""
        req = address.to_bytes(addr_bytes, "big") + size.to_bytes(size_bytes, "big")
        return self._send(Service.READ_MEMORY_BY_ADDRESS, req)

    # -- 0x27 SecurityAccess -------------------------------------------------
    def security_access_request_seed(self, level: int) -> bytes:
        """0x27 — request a seed (odd sub-function). Returns the seed bytes."""
        data = self._send(Service.SECURITY_ACCESS, bytes([level]))
        return data[1:]  # strip echoed access mode

    def security_access_send_key(self, level: int, key: bytes) -> None:
        """0x27 — send the computed key (even sub-function = seed level + 1)."""
        self._send(Service.SECURITY_ACCESS, bytes([level + 1]) + bytes(key))

    # -- 0x2C DynamicallyDefineLocalIdentifier ------------------------------
    def dynamically_define_local_identifier(self, lid: int, definition: bytes) -> bytes:
        """0x2C — dynamically define a local identifier's content."""
        return self._send(
            Service.DYNAMICALLY_DEFINE_LOCAL_IDENTIFIER,
            bytes([lid & 0xFF]) + bytes(definition),
        )

    # -- 0x2E WriteDataByCommonIdentifier -----------------------------------
    def write_data_by_common_identifier(self, did: int, data: bytes) -> None:
        """0x2E — write a record by common (2-byte) identifier."""
        self._send(
            Service.WRITE_DATA_BY_COMMON_IDENTIFIER,
            bytes([(did >> 8) & 0xFF, did & 0xFF]) + bytes(data),
        )

    # -- 0x3B WriteDataByLocalIdentifier ------------------------------------
    def write_data_by_local_identifier(self, lid: int, data: bytes) -> None:
        """0x3B — write a record by local identifier."""
        self._send(
            Service.WRITE_DATA_BY_LOCAL_IDENTIFIER,
            bytes([lid & 0xFF]) + bytes(data),
        )

    # -- 0x30 InputOutputControlByLocalIdentifier ---------------------------
    def input_output_control_by_local_identifier(self, lid: int,
                                                 control_parameter: int,
                                                 control_state: bytes = b"") -> bytes:
        """0x30 — control an actuator by local identifier."""
        req = bytes([lid & 0xFF, control_parameter]) + bytes(control_state)
        return self._send(Service.INPUT_OUTPUT_CONTROL_BY_LOCAL_IDENTIFIER, req)

    # -- 0x31 StartRoutineByLocalIdentifier ---------------------------------
    def start_routine_by_local_identifier(self, routine: int, data: bytes = b"") -> bytes:
        """0x31 — start a routine by local identifier. Strips echoed routine id."""
        resp = self._send(
            Service.START_ROUTINE_BY_LOCAL_IDENTIFIER,
            bytes([routine & 0xFF]) + bytes(data),
        )
        return resp[1:] if resp else b""

    # -- 0x32 StopRoutineByLocalIdentifier ----------------------------------
    def stop_routine_by_local_identifier(self, routine: int, data: bytes = b"") -> bytes:
        """0x32 — stop a routine by local identifier."""
        resp = self._send(
            Service.STOP_ROUTINE_BY_LOCAL_IDENTIFIER,
            bytes([routine & 0xFF]) + bytes(data),
        )
        return resp[1:] if resp else b""

    # -- 0x33 RequestRoutineResultsByLocalIdentifier ------------------------
    def request_routine_results_by_local_identifier(self, routine: int) -> bytes:
        """0x33 — request the results of a routine by local identifier."""
        resp = self._send(
            Service.REQUEST_ROUTINE_RESULTS_BY_LOCAL_IDENTIFIER,
            bytes([routine & 0xFF]),
        )
        return resp[1:] if resp else b""

    # -- 0x34 RequestDownload / 0x35 RequestUpload --------------------------
    def _request_transfer(self, sid: int, address: int, size: int,
                          data_format: int = 0x00, addr_bytes: int = 3,
                          size_bytes: int = 3) -> bytes:
        # KWP2000: memoryAddress(3) + dataFormatIdentifier(1) + uncompressedSize(3)
        req = (address.to_bytes(addr_bytes, "big")
               + bytes([data_format])
               + size.to_bytes(size_bytes, "big"))
        return self._send(sid, req)

    def request_download(self, address: int, size: int, **kw) -> bytes:
        """0x34 — request a download to the ECU. Returns maxNumberOfBlockLength."""
        return self._request_transfer(Service.REQUEST_DOWNLOAD, address, size, **kw)

    def request_upload(self, address: int, size: int, **kw) -> bytes:
        """0x35 — request an upload from the ECU."""
        return self._request_transfer(Service.REQUEST_UPLOAD, address, size, **kw)

    # -- 0x36 TransferData / 0x37 RequestTransferExit -----------------------
    def transfer_data(self, data: bytes = b"") -> bytes:
        """0x36 — transfer a data block."""
        return self._send(Service.TRANSFER_DATA, bytes(data))

    def request_transfer_exit(self, data: bytes = b"") -> bytes:
        """0x37 — signal end of a download/upload transfer."""
        return self._send(Service.REQUEST_TRANSFER_EXIT, bytes(data))

    # -- 0x3E TesterPresent --------------------------------------------------
    def tester_present(self, *, response_required: bool = False) -> None:
        """0x3E — keep the session alive.

        KWP2000 has no suppress-positive-response bit; instead it carries a
        response-required byte: ``0x01`` = respond, ``0x02`` = no response.
        """
        mode = (TesterPresentResponse.RESPONSE_REQUIRED if response_required
                else TesterPresentResponse.NO_RESPONSE_REQUIRED)
        self._send(
            Service.TESTER_PRESENT,
            bytes([mode]),
            expect_response=response_required,
        )
