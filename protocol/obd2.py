"""SAE J1979 OBD-II services — all ten diagnostic modes, transport-neutral.

Works over any :class:`~transport.base.Transport` (SocketCAN, ELM327, fake). The
transport delivers fully-reassembled service payloads, so there is no AT-command
handling, no ASCII scraping, and multi-ECU responses are aggregated.

Modes:
    0x01 current data          0x06 on-board monitor test results
    0x02 freeze-frame data     0x07 pending DTCs
    0x03 stored DTCs           0x08 control on-board component
    0x04 clear DTCs            0x09 vehicle information (VIN/CALID/CVN)
    0x05 O2 monitoring (legacy K-line; superseded by 0x06 on CAN)
    0x0A permanent DTCs

Module-level functions cover the common calls; :class:`J1979` bundles them all
against one transport.
"""
from __future__ import annotations

from enum import IntEnum

from transport.base import Transport

from .dtc import decode_dtc
from .dtc_library import lookup as _dtc_lookup
from .pids import PIDS, Value, decode_pid


class Mode(IntEnum):
    CURRENT_DATA = 0x01
    FREEZE_FRAME = 0x02
    STORED_DTCS = 0x03
    CLEAR_DTCS = 0x04
    O2_MONITORING = 0x05
    MONITOR_TEST_RESULTS = 0x06
    PENDING_DTCS = 0x07
    CONTROL_ONBOARD = 0x08
    VEHICLE_INFO = 0x09
    PERMANENT_DTCS = 0x0A


def _positive(responses, sid: int, pid: int | None = None):
    """Yield response payloads whose SID (and optional PID echo) match."""
    for r in responses:
        d = r.data
        if len(d) >= 1 and d[0] == sid + 0x40:
            if pid is None or (len(d) >= 2 and d[1] == pid):
                yield d


# --------------------------------------------------------------------------- #
#  Mode 0x01 — current data
# --------------------------------------------------------------------------- #
def read_pid(transport: Transport, pid: int, *, timeout: float = 1.0) -> Value | None:
    """Read and decode a single Mode 01 PID, e.g. ``read_pid(t, 0x0C)`` -> RPM."""
    for d in _positive(transport.request(bytes([0x01, pid]), timeout=timeout), 0x01, pid):
        value = decode_pid(pid, d[2:])
        if value is not None:
            return value
    return None


def read_supported_pids(transport: Transport, *, timeout: float = 1.0) -> set[int]:
    """Discover supported Mode 01 PIDs by walking the 0x00/0x20/... bitmasks."""
    supported: set[int] = set()
    base = 0x00
    while base <= 0xE0:
        bitmap = None
        for d in _positive(transport.request(bytes([0x01, base]), timeout=timeout), 0x01, base):
            if len(d) >= 6:
                bitmap = d[2:6]
                break
        if bitmap is None:
            break
        bits = int.from_bytes(bitmap, "big")
        for i in range(32):
            if bits & (1 << (31 - i)):
                supported.add(base + i + 1)
        if not bits & 0x1:  # low bit = "next range supported"
            break
        base += 0x20
    return supported


def scan_live_data(transport: Transport, *, timeout: float = 1.0) -> dict[str, str]:
    """Read every supported, known PID and return ``{name: "value unit"}``."""
    out: dict[str, str] = {}
    for pid in sorted(read_supported_pids(transport, timeout=timeout)):
        spec = PIDS.get(pid)
        if spec is None:
            continue
        value = read_pid(transport, pid, timeout=timeout)
        if value is not None:
            shown = f"{value:.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
            out[spec.name] = f"{shown} {spec.unit}".strip()
    return out


def read_engine_rpm(transport: Transport, *, timeout: float = 1.0) -> Value | None:
    return read_pid(transport, 0x0C, timeout=timeout)


def read_vehicle_speed(transport: Transport, *, timeout: float = 1.0) -> Value | None:
    return read_pid(transport, 0x0D, timeout=timeout)


def read_coolant_temp(transport: Transport, *, timeout: float = 1.0) -> Value | None:
    return read_pid(transport, 0x05, timeout=timeout)


# --------------------------------------------------------------------------- #
#  Mode 0x02 — freeze-frame data
# --------------------------------------------------------------------------- #
def read_freeze_frame(transport: Transport, pid: int, frame: int = 0,
                      *, timeout: float = 1.0) -> Value | None:
    """Mode 02 — a PID's value captured in freeze-frame ``frame`` (usually 0)."""
    req = bytes([0x02, pid, frame])
    for r in transport.request(req, timeout=timeout):
        d = r.data
        if len(d) >= 3 and d[0] == 0x42 and d[1] == pid and d[2] == frame:
            return decode_pid(pid, d[3:])
    return None


# --------------------------------------------------------------------------- #
#  Modes 0x03 / 0x07 / 0x0A — stored / pending / permanent DTCs
# --------------------------------------------------------------------------- #
def _read_dtcs(transport: Transport, mode: int, *, timeout: float) -> list[str]:
    codes: list[str] = []
    for d in _positive(transport.request(bytes([mode]), timeout=timeout), mode):
        codes.extend(_parse_dtc_payload(d))
    return codes


def _parse_dtc_payload(data: bytes) -> list[str]:
    # 4X <count> <hi lo> <hi lo> ...
    if len(data) < 2:
        return []
    count = data[1]
    body = data[2:]
    usable = min(count * 2, len(body) - (len(body) % 2))
    out: list[str] = []
    for i in range(0, usable, 2):
        code = decode_dtc(body[i], body[i + 1])
        if code != "P0000":
            out.append(code)
    return out


def read_dtcs(transport: Transport, *, timeout: float = 1.0) -> list[str]:
    """Mode 03 — stored/confirmed DTCs (codes only)."""
    return _read_dtcs(transport, Mode.STORED_DTCS, timeout=timeout)


def read_pending_dtcs(transport: Transport, *, timeout: float = 1.0) -> list[str]:
    """Mode 07 — DTCs detected during the current/last drive cycle."""
    return _read_dtcs(transport, Mode.PENDING_DTCS, timeout=timeout)


def read_permanent_dtcs(transport: Transport, *, timeout: float = 1.0) -> list[str]:
    """Mode 0A — permanent DTCs (cannot be cleared by a scan tool)."""
    return _read_dtcs(transport, Mode.PERMANENT_DTCS, timeout=timeout)


def describe_dtcs(codes: list[str], make: str | None = None) -> list[dict]:
    """Attach human definitions/categories from the DTC library to codes."""
    out = []
    for code in codes:
        entry = _dtc_lookup(code, make)
        out.append({
            "code": code,
            "definition": entry["definition"] if entry else "Manufacturer-specific or undocumented",
            "category": entry.get("category") if entry else None,
        })
    return out


# --------------------------------------------------------------------------- #
#  Mode 0x04 — clear DTCs / emissions data
# --------------------------------------------------------------------------- #
def clear_dtcs(transport: Transport, *, timeout: float = 1.0) -> bool:
    """Mode 04 — clear stored DTCs and freeze frames. True on a 0x44 ack."""
    for r in transport.request(bytes([0x04]), timeout=timeout):
        if r.data and r.data[0] == 0x44:
            return True
    return False


# --------------------------------------------------------------------------- #
#  Mode 0x06 — on-board monitor test results
# --------------------------------------------------------------------------- #
def read_monitor_test_results(transport: Transport, obdmid: int,
                              *, timeout: float = 1.0) -> list[dict]:
    """Mode 06 — test results for a monitor id (OBDMID). Returns raw records.

    Each record: ``{obdmid, tid, unit_scaling, value, min, max}`` (raw 16-bit
    values; scaling per the UAS id is left to the caller).
    """
    results: list[dict] = []
    for d in _positive(transport.request(bytes([0x06, obdmid]), timeout=timeout), 0x06):
        body = d[1:]  # drop SID; records are 9 bytes: MID,TID,UAS,val(2),min(2),max(2)
        for i in range(0, len(body) - (len(body) % 9), 9):
            rec = body[i:i + 9]
            results.append({
                "obdmid": rec[0],
                "tid": rec[1],
                "unit_scaling": rec[2],
                "value": (rec[3] << 8) | rec[4],
                "min": (rec[5] << 8) | rec[6],
                "max": (rec[7] << 8) | rec[8],
            })
    return results


# --------------------------------------------------------------------------- #
#  Mode 0x08 — control operation of on-board component/system
# --------------------------------------------------------------------------- #
def request_control(transport: Transport, tid: int, data: bytes = b"",
                    *, timeout: float = 1.0) -> bytes | None:
    """Mode 08 — request control of an on-board system (TID + optional data)."""
    req = bytes([0x08, tid]) + bytes(data)
    for r in transport.request(req, timeout=timeout):
        if len(r.data) >= 2 and r.data[0] == 0x48 and r.data[1] == tid:
            return r.data[2:]
    return None


# --------------------------------------------------------------------------- #
#  Mode 0x09 — vehicle information
# --------------------------------------------------------------------------- #
def _read_info_string(transport: Transport, pid: int, *, timeout: float) -> str | None:
    for r in transport.request(bytes([0x09, pid]), timeout=timeout):
        d = r.data
        if len(d) >= 3 and d[0] == 0x49 and d[1] == pid:
            raw = d[3:]  # drop SID, PID, message-count byte
            text = bytes(b for b in raw if 0x20 <= b <= 0x7E).decode("ascii", "ignore").strip()
            if text:
                return text
    return None


def read_vin(transport: Transport, *, timeout: float = 2.0) -> str | None:
    """Mode 09 PID 02 — Vehicle Identification Number (multi-frame)."""
    return _read_info_string(transport, 0x02, timeout=timeout)


def read_calibration_ids(transport: Transport, *, timeout: float = 2.0) -> str | None:
    """Mode 09 PID 04 — Calibration Identification(s)."""
    return _read_info_string(transport, 0x04, timeout=timeout)


def read_cvn(transport: Transport, *, timeout: float = 1.0) -> str | None:
    """Mode 09 PID 06 — Calibration Verification Number(s), as hex."""
    for r in transport.request(bytes([0x09, 0x06]), timeout=timeout):
        d = r.data
        if len(d) >= 3 and d[0] == 0x49 and d[1] == 0x06:
            return d[3:].hex().upper() or None
    return None


# --------------------------------------------------------------------------- #
#  Client bundle
# --------------------------------------------------------------------------- #
class J1979:
    """All OBD-II modes bound to one transport."""

    def __init__(self, transport: Transport, *, make: str | None = None):
        self._t = transport
        self.make = make

    # live data
    def supported_pids(self) -> set[int]:
        return read_supported_pids(self._t)

    def read_pid(self, pid: int) -> Value | None:
        return read_pid(self._t, pid)

    def live_data(self) -> dict[str, str]:
        return scan_live_data(self._t)

    def freeze_frame(self, pid: int, frame: int = 0) -> Value | None:
        return read_freeze_frame(self._t, pid, frame)

    # DTCs
    def stored_dtcs(self, *, detailed: bool = False):
        codes = read_dtcs(self._t)
        return describe_dtcs(codes, self.make) if detailed else codes

    def pending_dtcs(self, *, detailed: bool = False):
        codes = read_pending_dtcs(self._t)
        return describe_dtcs(codes, self.make) if detailed else codes

    def permanent_dtcs(self, *, detailed: bool = False):
        codes = read_permanent_dtcs(self._t)
        return describe_dtcs(codes, self.make) if detailed else codes

    def clear_dtcs(self) -> bool:
        return clear_dtcs(self._t)

    # monitors / control / info
    def monitor_test_results(self, obdmid: int) -> list[dict]:
        return read_monitor_test_results(self._t, obdmid)

    def request_control(self, tid: int, data: bytes = b"") -> bytes | None:
        return request_control(self._t, tid, data)

    def vin(self) -> str | None:
        return read_vin(self._t)

    def calibration_ids(self) -> str | None:
        return read_calibration_ids(self._t)

    def cvn(self) -> str | None:
        return read_cvn(self._t)
