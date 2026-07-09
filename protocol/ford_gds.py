"""Ford CAN Generic Diagnostic Specification (GDS), ~2003 era.

Ford's CAN GDS is *not* a new protocol: it is the ISO 14230 (KWP2000) service
layer carried over CAN / ISO-TP, with Ford-specific 11-bit CAN addressing and a
Ford-specific catalog of LIDs (0x21), common identifiers / DIDs (0x22) and ECU
identification options (0x1A). This module therefore reuses the authoritative
:class:`~protocol.kwp2000.KWP2000Client` unchanged and only adds:

  * a :class:`FordModule` address map (11-bit physical request / response CAN IDs);
  * a thin :class:`FordGDS` facade that binds a KWP2000 client to one module and
    exposes the everyday GDS operations (session, VIN, calibration, DTCs, ...);
  * a small catalog of commonly-observed Ford identifiers.

PROVENANCE / HONESTY
--------------------
The **service layer** (SIDs, request/response framing, NRC handling) is
authoritative — it is ISO 14230-3 (KWP2000) and lives in :mod:`protocol.kwp2000`.

The **CAN addressing** values that are standardised by ISO 15765-4 (OBD-II over
CAN) are authoritative:

    * PCM / ECM physical request  = 0x7E0, response = 0x7E8
    * second powertrain ECU (TCM) request = 0x7E1, response = 0x7E9
    * OBD-II functional (broadcast) request = 0x7DF

Everything else in :class:`FordModule` (ABS, RCM/airbag, IPC, BCM, PAM, ...) is
**community-documented / commonly-observed**, NOT taken from an authoritative
public Ford spec. Ford's per-module 11-bit IDs vary by vehicle line, model year
and network topology (HS-CAN vs MS-CAN), and on real vehicles these modules are
often reached through a gateway. Treat every address marked ``# inferred`` below
as a sensible default to be confirmed against the specific vehicle, not fact.

The identifier catalog (:data:`FORD_DIDS`, :data:`FORD_LIDS`,
:data:`FORD_ECU_ID_OPTIONS`) mixes ISO-standard DIDs (authoritative, e.g. VIN =
0xF190) with commonly-observed Ford values (inferred); each entry says which.

    from transport.socketcan import SocketCanTransport
    from protocol.ford_gds import FordGDS, FordModule

    with SocketCanTransport("can0", ecu=0) as t:
        gds = FordGDS(t, module=FordModule.PCM)
        gds.enter_extended_session()
        print(gds.read_vin())
        print(gds.read_calibration_level())
"""
from __future__ import annotations

from enum import Enum

from transport.base import Transport

from .kwp2000 import KWP2000Client, Session


# --------------------------------------------------------------------------- #
#  Module address map (11-bit physical request / response CAN IDs).
#
#  AUTHORITATIVE (ISO 15765-4): PCM 0x7E0/0x7E8, TCM 0x7E1/0x7E9,
#  functional broadcast 0x7DF.
#  INFERRED (community-documented, confirm per vehicle): everything else.
# --------------------------------------------------------------------------- #
class FordModule(Enum):
    """A Ford diagnostic module and its 11-bit request/response CAN IDs.

    Each member value is ``(request_id, response_id, authoritative)`` where
    ``authoritative`` is True only for the ISO 15765-4 standardised powertrain
    addresses. All other entries are commonly-observed defaults ("inferred").
    """

    # -- authoritative (ISO 15765-4 legislated OBD powertrain addressing) -----
    PCM = (0x7E0, 0x7E8, True)   # Powertrain Control Module (ECM) — authoritative
    TCM = (0x7E1, 0x7E9, True)   # Transmission Control Module    — authoritative

    # -- inferred (community-documented; vary by vehicle line / MY / bus) ------
    ABS = (0x760, 0x768, False)  # Anti-lock Braking System            # inferred
    RCM = (0x737, 0x73F, False)  # Restraint Control Module (airbag)   # inferred
    IPC = (0x720, 0x728, False)  # Instrument Panel Cluster            # inferred
    BCM = (0x726, 0x72E, False)  # Body Control Module                 # inferred
    PAM = (0x736, 0x73E, False)  # Parking Aid Module                  # inferred
    ACM = (0x727, 0x72F, False)  # Audio Control Module                # inferred
    HVAC = (0x733, 0x73B, False)  # Climate control (HVAC)             # inferred

    def __init__(self, request_id: int, response_id: int, authoritative: bool):
        self.request_id = request_id
        self.response_id = response_id
        self.authoritative = authoritative

    @property
    def is_inferred(self) -> bool:
        """True if this address is community-observed, not from a public spec."""
        return not self.authoritative


# --------------------------------------------------------------------------- #
#  Identifier catalog. Each constant carries a provenance note.
# --------------------------------------------------------------------------- #

# 0x22 ReadDataByCommonIdentifier (DID) — 2-byte identifiers.
#   AUTHORITATIVE (ISO 14229-1 / ISO 15765 standard DID range 0xF1xx):
FORD_DID_VIN = 0xF190              # VIN — ISO-standard DID (authoritative)
FORD_DID_ECU_HW_NUMBER = 0xF191    # ECU hardware number — ISO-standard (authoritative)
FORD_DID_SUPPLIER_ECU_SW_NUMBER = 0xF194  # ECU software number — ISO-standard (authoritative)
FORD_DID_ECU_SERIAL_NUMBER = 0xF18C  # ECU serial number — ISO-standard (authoritative)
#   INFERRED (commonly-observed Ford strategy/calibration DIDs; confirm per ECU):
FORD_DID_CALIBRATION_LEVEL = 0xF124   # Calibration level/version — inferred
FORD_DID_STRATEGY_PART_NUMBER = 0xF111  # Strategy (SW) part number — inferred
FORD_DID_CALIBRATION_PART_NUMBER = 0xF110  # Calibration part number — inferred

#: DID catalog with human-readable names + provenance (True = authoritative).
FORD_DIDS: dict[int, tuple[str, bool]] = {
    FORD_DID_VIN: ("VIN", True),
    FORD_DID_ECU_HW_NUMBER: ("ECU hardware number", True),
    FORD_DID_SUPPLIER_ECU_SW_NUMBER: ("ECU software number", True),
    FORD_DID_ECU_SERIAL_NUMBER: ("ECU serial number", True),
    FORD_DID_CALIBRATION_LEVEL: ("Calibration level", False),
    FORD_DID_STRATEGY_PART_NUMBER: ("Strategy part number", False),
    FORD_DID_CALIBRATION_PART_NUMBER: ("Calibration part number", False),
}

# 0x21 ReadDataByLocalIdentifier (LID) — 1-byte identifiers.
#   All INFERRED: Ford LID assignments are proprietary and vary by module.
FORD_LID_VEHICLE_ID_BLOCK = 0x01   # Vehicle identification block — inferred
FORD_LID_CALIBRATION_BLOCK = 0x02  # Calibration ID block — inferred

#: LID catalog (all commonly-observed / inferred, per note above).
FORD_LIDS: dict[int, tuple[str, bool]] = {
    FORD_LID_VEHICLE_ID_BLOCK: ("Vehicle identification block", False),
    FORD_LID_CALIBRATION_BLOCK: ("Calibration ID block", False),
}

# 0x1A ReadEcuIdentification options.
#   Option 0x80..0x9F range is KWP2000-defined but the *content* per option is
#   OEM-specific. These option numbers are INFERRED for Ford (confirm per ECU).
FORD_ECU_ID_PART_NUMBER = 0x87     # ECU/part number record — inferred
FORD_ECU_ID_CALIBRATION = 0x88     # Calibration identification record — inferred

#: ReadEcuIdentification option catalog (inferred).
FORD_ECU_ID_OPTIONS: dict[int, tuple[str, bool]] = {
    FORD_ECU_ID_PART_NUMBER: ("ECU part number", False),
    FORD_ECU_ID_CALIBRATION: ("Calibration identification", False),
}


class FordGDS:
    """Ford CAN GDS facade: a KWP2000 client bound to one :class:`FordModule`.

    All diagnostic behaviour is delegated to :class:`~protocol.kwp2000.KWP2000Client`
    — this class only picks the right module addressing and the right Ford
    identifiers, so nothing about the authoritative KWP2000 service layer is
    re-implemented here.

    Args:
        transport: an open :class:`~transport.base.Transport`. It is expected to
            be (or to be configured for) this module's physical addressing; the
            request/response CAN IDs live on ``module`` for callers that build the
            transport themselves.
        module:    which module to talk to (default :attr:`FordModule.PCM`).
    """

    def __init__(self, transport: Transport, module: FordModule = FordModule.PCM,
                 **client_kwargs):
        self.module = module
        self.request_id = module.request_id
        self.response_id = module.response_id
        self.kwp = KWP2000Client(transport, **client_kwargs)

    # -- sessions -----------------------------------------------------------
    def enter_extended_session(self) -> bytes:
        """0x10 0x92 — enter the KWP2000 extended diagnostic session."""
        return self.kwp.start_diagnostic_session(Session.EXTENDED)

    def enter_default_session(self) -> bytes:
        """0x10 0x81 — return to the standard/default session."""
        return self.kwp.start_diagnostic_session(Session.STANDARD)

    def tester_present(self, *, response_required: bool = False) -> None:
        """0x3E — keep the session alive (KWP2000 response-required byte)."""
        self.kwp.tester_present(response_required=response_required)

    # -- security -----------------------------------------------------------
    def security_access_request_seed(self, level: int = 0x01) -> bytes:
        """0x27 (odd sub-function) — request a security seed. Returns seed bytes."""
        return self.kwp.security_access_request_seed(level)

    def security_access_send_key(self, level: int, key: bytes) -> None:
        """0x27 (even sub-function) — send the computed key."""
        self.kwp.security_access_send_key(level, key)

    def security_access(self, level: int = 0x01):
        """Convenience: return the seed for ``level``.

        Ford's seed→key algorithm is proprietary and vehicle/module specific, so
        this facade cannot compute the key. Callers request the seed here, run
        their own key function, then call :meth:`security_access_send_key`.
        """
        return self.security_access_request_seed(level)

    # -- identification reads -----------------------------------------------
    def read_data_by_identifier(self, did: int) -> bytes:
        """0x22 — read a Ford common identifier (DID). Returns the record bytes."""
        return self.kwp.read_data_by_common_identifier(did)

    def read_data_by_local_identifier(self, lid: int) -> bytes:
        """0x21 — read a Ford local identifier (LID) record."""
        return self.kwp.read_data_by_local_identifier(lid)

    def read_vin(self) -> str:
        """Read the VIN via DID 0xF190 (ISO-standard) and decode to ASCII.

        Trailing NULs / padding are stripped; non-ASCII bytes are dropped.
        """
        raw = self.read_data_by_identifier(FORD_DID_VIN)
        return raw.rstrip(b"\x00").decode("ascii", errors="ignore").strip()

    def read_calibration_level(self) -> str:
        """Read the calibration level via DID 0xF124.

        NOTE: DID 0xF124 is a commonly-observed / inferred Ford value, not from an
        authoritative public spec. Returned as a stripped ASCII string.
        """
        raw = self.read_data_by_identifier(FORD_DID_CALIBRATION_LEVEL)
        return raw.rstrip(b"\x00").decode("ascii", errors="ignore").strip()

    def read_part_number(self, did: int = FORD_DID_STRATEGY_PART_NUMBER) -> str:
        """Read a part number DID (default strategy part number 0xF111).

        NOTE: Ford strategy/calibration part-number DIDs are commonly-observed /
        inferred. Returned as a stripped ASCII string.
        """
        raw = self.read_data_by_identifier(did)
        return raw.rstrip(b"\x00").decode("ascii", errors="ignore").strip()

    # -- DTCs ---------------------------------------------------------------
    def read_dtcs(self, status: int = 0x00, group: int = 0xFF00) -> list[dict]:
        """0x18 ReadDTCsByStatus — returns ``[{code, status, flags}]``."""
        return self.kwp.read_dtcs_by_status(status, group)

    def clear_dtcs(self, group: int = 0xFF00) -> None:
        """0x14 ClearDiagnosticInformation — clear DTCs for ``group`` (all by default)."""
        self.kwp.clear_diagnostic_information(group)
