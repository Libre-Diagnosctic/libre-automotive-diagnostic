"""ISO 14229-1 (UDS) client — full diagnostic service coverage.

A thin, transport-neutral client. Each method builds the request PDU, sends it
via a :class:`~transport.base.Transport` (physically addressed to one ECU), and
returns the parsed positive-response payload. Negative responses raise
:class:`NegativeResponseError`; response-pending (NRC 0x78) is awaited transparently.

    from transport.socketcan import SocketCanTransport
    from protocol.uds import UDSClient, Session, ResetType

    with SocketCanTransport("can0", ecu=0) as t:
        uds = UDSClient(t)
        uds.diagnostic_session_control(Session.EXTENDED)
        vin = uds.read_data_by_identifier(0xF190)
        seed = uds.security_access_request_seed(1)
        uds.security_access_send_key(1, my_key_fn(seed))
"""
from __future__ import annotations

from enum import IntEnum

from transport.base import Transport

from .dtc import decode_dtc
from .nrc import NRC, RESPONSE_PENDING  # canonical 0x7F code table

SUPPRESS_POS_RSP_BIT = 0x80  # OR into a sub-function byte to suppress the positive reply


# --------------------------------------------------------------------------- #
#  Service IDs (request SIDs). Positive response SID = request SID + 0x40.
# --------------------------------------------------------------------------- #
class Service(IntEnum):
    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    CLEAR_DIAGNOSTIC_INFORMATION = 0x14
    READ_DTC_INFORMATION = 0x19
    READ_DATA_BY_IDENTIFIER = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    READ_SCALING_DATA_BY_IDENTIFIER = 0x24
    SECURITY_ACCESS = 0x27
    COMMUNICATION_CONTROL = 0x28
    AUTHENTICATION = 0x29
    READ_DATA_BY_PERIODIC_IDENTIFIER = 0x2A
    DYNAMICALLY_DEFINE_DATA_IDENTIFIER = 0x2C
    WRITE_DATA_BY_IDENTIFIER = 0x2E
    INPUT_OUTPUT_CONTROL_BY_IDENTIFIER = 0x2F
    ROUTINE_CONTROL = 0x31
    REQUEST_DOWNLOAD = 0x34
    REQUEST_UPLOAD = 0x35
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37
    REQUEST_FILE_TRANSFER = 0x38
    WRITE_MEMORY_BY_ADDRESS = 0x3D
    TESTER_PRESENT = 0x3E
    ACCESS_TIMING_PARAMETER = 0x83
    SECURED_DATA_TRANSMISSION = 0x84
    CONTROL_DTC_SETTING = 0x85
    RESPONSE_ON_EVENT = 0x86
    LINK_CONTROL = 0x87


class Session(IntEnum):
    DEFAULT = 0x01
    PROGRAMMING = 0x02
    EXTENDED = 0x03
    SAFETY_SYSTEM = 0x04


class ResetType(IntEnum):
    HARD = 0x01
    KEY_OFF_ON = 0x02
    SOFT = 0x03
    ENABLE_RAPID_POWER_SHUTDOWN = 0x04
    DISABLE_RAPID_POWER_SHUTDOWN = 0x05


class RoutineControlType(IntEnum):
    START = 0x01
    STOP = 0x02
    REQUEST_RESULTS = 0x03


class DtcReportType(IntEnum):
    NUMBER_BY_STATUS_MASK = 0x01
    BY_STATUS_MASK = 0x02
    SNAPSHOT_IDENTIFICATION = 0x03
    SNAPSHOT_BY_DTC = 0x04
    EXTENDED_DATA_BY_DTC = 0x06
    SUPPORTED_DTC = 0x0A
    FIRST_CONFIRMED_DTC = 0x0C
    MOST_RECENT_CONFIRMED_DTC = 0x0E


class DtcSettingType(IntEnum):
    ON = 0x01
    OFF = 0x02


class CommunicationControlType(IntEnum):
    ENABLE_RX_TX = 0x00
    ENABLE_RX_DISABLE_TX = 0x01
    DISABLE_RX_ENABLE_TX = 0x02
    DISABLE_RX_TX = 0x03


# Negative Response Codes (0x7F) live in protocol/nrc.py — the canonical table
# (ISO 14229-1 + legacy KWP block-transfer codes). NRC and RESPONSE_PENDING are
# imported above and re-used here so there is one source of truth.

# DTC status bit meanings (ISO 14229-1 Annex D.2).
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


class UdsError(Exception):
    """Base class for UDS-layer errors."""


class UdsTimeoutError(UdsError):
    """The ECU did not respond within the timeout."""


class UnexpectedResponseError(UdsError):
    """The response SID did not match the request."""


class NegativeResponseError(UdsError):
    """The ECU returned ``7F <sid> <nrc>``."""

    def __init__(self, request_sid: int, nrc: int):
        self.request_sid = request_sid
        self.nrc = nrc
        self.nrc_name = NRC.get(nrc, "unknown")
        super().__init__(
            f"UDS 0x{request_sid:02X} negative response: "
            f"0x{nrc:02X} {self.nrc_name}"
        )


def decode_uds_dtc(hi: int, mid: int, lo: int) -> str:
    """3-byte UDS DTC -> ``"P0301-00"`` (base code + fault-type byte)."""
    return f"{decode_dtc(hi, mid)}-{lo:02X}"


def decode_dtc_status(status: int) -> dict[str, bool]:
    """Decode a DTC status byte into named flags (ISO 14229-1 Annex D)."""
    return {name: bool(status & (1 << i)) for i, name in enumerate(_STATUS_BITS)}


class UDSClient:
    """ISO 14229-1 client over one physically-addressed ECU."""

    def __init__(self, transport: Transport, *, p2: float = 1.0, p2_star: float = 5.0,
                 max_pending: int = 10):
        self._t = transport
        self.p2 = p2
        self.p2_star = p2_star
        self.max_pending = max_pending

    # -- core request/response ----------------------------------------------
    def _send(self, sid: int, data: bytes = b"", *, expect_response: bool = True) -> bytes:
        payload = bytes([sid]) + bytes(data)
        responses = self._t.request(payload, functional=False, timeout=self.p2)
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
        raise UdsTimeoutError("no response from ECU")

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
                raise UdsTimeoutError("too many responsePending (0x78) replies")
            more = self._t.receive(timeout=self.p2_star)
            resp = self._pick(more)
        return resp

    def _check(self, resp: bytes, sid: int) -> None:
        if resp and resp[0] == 0x7F:
            nrc = resp[2] if len(resp) >= 3 else 0x10
            raise NegativeResponseError(sid, nrc)
        if not resp or resp[0] != (sid + 0x40) & 0xFF:
            got = resp[0] if resp else None
            raise UnexpectedResponseError(
                f"expected response SID 0x{(sid + 0x40) & 0xFF:02X}, got "
                f"{'0x%02X' % got if got is not None else 'nothing'}"
            )

    @staticmethod
    def _subfn(value: int, suppress: bool) -> int:
        return (value | SUPPRESS_POS_RSP_BIT) if suppress else value

    # -- 0x10 DiagnosticSessionControl --------------------------------------
    def diagnostic_session_control(self, session: int, *, suppress_response: bool = False) -> dict:
        data = self._send(
            Service.DIAGNOSTIC_SESSION_CONTROL,
            bytes([self._subfn(session, suppress_response)]),
            expect_response=not suppress_response,
        )
        out: dict = {"session": session}
        if len(data) >= 5:  # echoed session + P2(2) + P2*(2)
            out["p2_ms"] = (data[1] << 8) | data[2]
            out["p2_star_ms"] = ((data[3] << 8) | data[4]) * 10
        return out

    # -- 0x11 ECUReset -------------------------------------------------------
    def ecu_reset(self, reset_type: int = ResetType.HARD, *, suppress_response: bool = False) -> bytes:
        return self._send(
            Service.ECU_RESET,
            bytes([self._subfn(reset_type, suppress_response)]),
            expect_response=not suppress_response,
        )

    # -- 0x14 ClearDiagnosticInformation ------------------------------------
    def clear_diagnostic_information(self, group: int = 0xFFFFFF) -> None:
        self._send(
            Service.CLEAR_DIAGNOSTIC_INFORMATION,
            bytes([(group >> 16) & 0xFF, (group >> 8) & 0xFF, group & 0xFF]),
        )

    # -- 0x19 ReadDTCInformation --------------------------------------------
    def read_dtc_information(self, subfunction: int, data: bytes = b"") -> bytes:
        return self._send(Service.READ_DTC_INFORMATION, bytes([subfunction]) + bytes(data))

    def read_dtcs_by_status_mask(self, status_mask: int = 0xFF) -> list[dict]:
        """0x19/0x02 — DTCs matching a status mask. Returns [{code, status, flags}]."""
        data = self.read_dtc_information(DtcReportType.BY_STATUS_MASK, bytes([status_mask]))
        # data = subfn + statusAvailabilityMask + N*(DTC[3] + status[1])
        records = data[2:]
        out: list[dict] = []
        for i in range(0, len(records) - (len(records) % 4), 4):
            hi, mid, lo, status = records[i], records[i + 1], records[i + 2], records[i + 3]
            out.append({
                "code": decode_uds_dtc(hi, mid, lo),
                "status": status,
                "flags": decode_dtc_status(status),
            })
        return out

    def read_supported_dtcs(self) -> list[dict]:
        """0x19/0x0A — all DTCs supported by the ECU."""
        data = self.read_dtc_information(DtcReportType.SUPPORTED_DTC)
        records = data[2:]
        out: list[dict] = []
        for i in range(0, len(records) - (len(records) % 4), 4):
            hi, mid, lo, status = records[i], records[i + 1], records[i + 2], records[i + 3]
            out.append({"code": decode_uds_dtc(hi, mid, lo), "status": status})
        return out

    # -- 0x22 ReadDataByIdentifier ------------------------------------------
    def read_data_by_identifier(self, did: int) -> bytes:
        data = self._send(
            Service.READ_DATA_BY_IDENTIFIER, bytes([(did >> 8) & 0xFF, did & 0xFF])
        )
        # data = DID(2) + record; strip the echoed DID.
        return data[2:] if len(data) >= 2 else b""

    # -- 0x23 ReadMemoryByAddress -------------------------------------------
    def read_memory_by_address(self, address: int, size: int,
                               *, addr_bytes: int = 4, size_bytes: int = 2) -> bytes:
        alfid = (size_bytes << 4) | addr_bytes
        req = bytes([alfid]) + address.to_bytes(addr_bytes, "big") + size.to_bytes(size_bytes, "big")
        return self._send(Service.READ_MEMORY_BY_ADDRESS, req)

    # -- 0x24 ReadScalingDataByIdentifier -----------------------------------
    def read_scaling_data_by_identifier(self, did: int) -> bytes:
        return self._send(
            Service.READ_SCALING_DATA_BY_IDENTIFIER, bytes([(did >> 8) & 0xFF, did & 0xFF])
        )

    # -- 0x27 SecurityAccess -------------------------------------------------
    def security_access_request_seed(self, level: int) -> bytes:
        """Request a seed (odd sub-function). Returns the seed bytes."""
        data = self._send(Service.SECURITY_ACCESS, bytes([level]))
        return data[1:]  # strip echoed access level

    def security_access_send_key(self, level: int, key: bytes) -> None:
        """Send the computed key (even sub-function = seed level + 1)."""
        self._send(Service.SECURITY_ACCESS, bytes([level + 1]) + bytes(key))

    # -- 0x28 CommunicationControl ------------------------------------------
    def communication_control(self, control_type: int, communication_type: int = 0x01,
                              *, suppress_response: bool = False) -> bytes:
        return self._send(
            Service.COMMUNICATION_CONTROL,
            bytes([self._subfn(control_type, suppress_response), communication_type]),
            expect_response=not suppress_response,
        )

    # -- 0x29 Authentication -------------------------------------------------
    def authentication(self, subfunction: int, data: bytes = b"") -> bytes:
        return self._send(Service.AUTHENTICATION, bytes([subfunction]) + bytes(data))

    # -- 0x2A ReadDataByPeriodicIdentifier ----------------------------------
    def read_data_by_periodic_identifier(self, transmission_mode: int,
                                         periodic_dids: bytes) -> bytes:
        return self._send(
            Service.READ_DATA_BY_PERIODIC_IDENTIFIER,
            bytes([transmission_mode]) + bytes(periodic_dids),
        )

    # -- 0x2C DynamicallyDefineDataIdentifier -------------------------------
    def dynamically_define_data_identifier(self, subfunction: int, data: bytes) -> bytes:
        return self._send(
            Service.DYNAMICALLY_DEFINE_DATA_IDENTIFIER, bytes([subfunction]) + bytes(data)
        )

    # -- 0x2E WriteDataByIdentifier -----------------------------------------
    def write_data_by_identifier(self, did: int, data: bytes) -> None:
        self._send(
            Service.WRITE_DATA_BY_IDENTIFIER,
            bytes([(did >> 8) & 0xFF, did & 0xFF]) + bytes(data),
        )

    # -- 0x2F InputOutputControlByIdentifier --------------------------------
    def io_control_by_identifier(self, did: int, control_parameter: int,
                                 control_state: bytes = b"") -> bytes:
        req = bytes([(did >> 8) & 0xFF, did & 0xFF, control_parameter]) + bytes(control_state)
        return self._send(Service.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER, req)

    # -- 0x31 RoutineControl -------------------------------------------------
    def routine_control(self, control_type: int, routine_id: int, data: bytes = b"") -> bytes:
        req = bytes([control_type, (routine_id >> 8) & 0xFF, routine_id & 0xFF]) + bytes(data)
        return self._send(Service.ROUTINE_CONTROL, req)

    def start_routine(self, routine_id: int, data: bytes = b"") -> bytes:
        return self.routine_control(RoutineControlType.START, routine_id, data)

    def stop_routine(self, routine_id: int, data: bytes = b"") -> bytes:
        return self.routine_control(RoutineControlType.STOP, routine_id, data)

    def routine_results(self, routine_id: int) -> bytes:
        return self.routine_control(RoutineControlType.REQUEST_RESULTS, routine_id)

    # -- 0x34 RequestDownload / 0x35 RequestUpload --------------------------
    def _request_transfer(self, sid: int, address: int, size: int,
                          data_format: int = 0x00, addr_bytes: int = 4,
                          size_bytes: int = 4) -> int:
        alfid = (size_bytes << 4) | addr_bytes
        req = (bytes([data_format, alfid])
               + address.to_bytes(addr_bytes, "big")
               + size.to_bytes(size_bytes, "big"))
        resp = self._send(sid, req)
        # resp = lengthFormatId + maxNumberOfBlockLength(...)
        if not resp:
            return 0
        n = (resp[0] >> 4) & 0x0F
        return int.from_bytes(resp[1 : 1 + n], "big") if n else 0

    def request_download(self, address: int, size: int, **kw) -> int:
        """Returns the ECU's max block length for TransferData."""
        return self._request_transfer(Service.REQUEST_DOWNLOAD, address, size, **kw)

    def request_upload(self, address: int, size: int, **kw) -> int:
        return self._request_transfer(Service.REQUEST_UPLOAD, address, size, **kw)

    # -- 0x36 TransferData / 0x37 RequestTransferExit -----------------------
    def transfer_data(self, block_sequence_counter: int, data: bytes = b"") -> bytes:
        return self._send(
            Service.TRANSFER_DATA, bytes([block_sequence_counter & 0xFF]) + bytes(data)
        )

    def request_transfer_exit(self, data: bytes = b"") -> bytes:
        return self._send(Service.REQUEST_TRANSFER_EXIT, bytes(data))

    # -- 0x38 RequestFileTransfer -------------------------------------------
    def request_file_transfer(self, mode_of_operation: int, data: bytes) -> bytes:
        return self._send(Service.REQUEST_FILE_TRANSFER, bytes([mode_of_operation]) + bytes(data))

    # -- 0x3D WriteMemoryByAddress ------------------------------------------
    def write_memory_by_address(self, address: int, data: bytes,
                                *, addr_bytes: int = 4, size_bytes: int = 2) -> bytes:
        alfid = (size_bytes << 4) | addr_bytes
        req = (bytes([alfid])
               + address.to_bytes(addr_bytes, "big")
               + len(data).to_bytes(size_bytes, "big")
               + bytes(data))
        return self._send(Service.WRITE_MEMORY_BY_ADDRESS, req)

    # -- 0x3E TesterPresent --------------------------------------------------
    def tester_present(self, *, suppress_response: bool = True) -> None:
        self._send(
            Service.TESTER_PRESENT,
            bytes([self._subfn(0x00, suppress_response)]),
            expect_response=not suppress_response,
        )

    # -- 0x83 AccessTimingParameter -----------------------------------------
    def access_timing_parameter(self, access_type: int, request_record: bytes = b"") -> bytes:
        return self._send(
            Service.ACCESS_TIMING_PARAMETER, bytes([access_type]) + bytes(request_record)
        )

    # -- 0x84 SecuredDataTransmission ---------------------------------------
    def secured_data_transmission(self, data: bytes) -> bytes:
        return self._send(Service.SECURED_DATA_TRANSMISSION, bytes(data))

    # -- 0x85 ControlDTCSetting ---------------------------------------------
    def control_dtc_setting(self, setting_type: int, data: bytes = b"",
                            *, suppress_response: bool = False) -> None:
        self._send(
            Service.CONTROL_DTC_SETTING,
            bytes([self._subfn(setting_type, suppress_response)]) + bytes(data),
            expect_response=not suppress_response,
        )

    # -- 0x86 ResponseOnEvent -----------------------------------------------
    def response_on_event(self, event_type: int, data: bytes = b"",
                          *, suppress_response: bool = False) -> bytes:
        return self._send(
            Service.RESPONSE_ON_EVENT,
            bytes([self._subfn(event_type, suppress_response)]) + bytes(data),
            expect_response=not suppress_response,
        )

    # -- 0x87 LinkControl ----------------------------------------------------
    def link_control(self, control_type: int, data: bytes = b"",
                     *, suppress_response: bool = False) -> bytes:
        return self._send(
            Service.LINK_CONTROL,
            bytes([self._subfn(control_type, suppress_response)]) + bytes(data),
            expect_response=not suppress_response,
        )
