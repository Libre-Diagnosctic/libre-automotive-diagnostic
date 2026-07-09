"""SAE J1979 Mode 01 PID table — data-driven decoders.

Each PID maps to a :class:`Pid` with its byte count, unit, and a decode function
that turns the value bytes (``A = data[0]``, ``B = data[1]``, ...) into an
engineering value. Formulas are the standard J1979 set — the same math the old
``obd_formulas.c`` got right — kept in one table so the transport backends and
the simulator agree by construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

Value = Union[float, int]


@dataclass(frozen=True)
class Pid:
    pid: int
    name: str
    n_bytes: int
    unit: str
    decode: Callable[[bytes], Value]


def _pid(pid: int, name: str, n_bytes: int, unit: str, fn: Callable[[bytes], Value]) -> Pid:
    return Pid(pid, name, n_bytes, unit, fn)


# A = data[0], B = data[1], C = data[2], D = data[3]
PIDS: dict[int, Pid] = {p.pid: p for p in [
    _pid(0x04, "Calculated Engine Load", 1, "%",   lambda d: d[0] * 100.0 / 255.0),
    _pid(0x05, "Coolant Temperature",    1, "degC", lambda d: d[0] - 40),
    _pid(0x06, "Short Fuel Trim B1",     1, "%",   lambda d: d[0] * 100.0 / 128.0 - 100.0),
    _pid(0x07, "Long Fuel Trim B1",      1, "%",   lambda d: d[0] * 100.0 / 128.0 - 100.0),
    _pid(0x08, "Short Fuel Trim B2",     1, "%",   lambda d: d[0] * 100.0 / 128.0 - 100.0),
    _pid(0x09, "Long Fuel Trim B2",      1, "%",   lambda d: d[0] * 100.0 / 128.0 - 100.0),
    _pid(0x0A, "Fuel Pressure",          1, "kPa", lambda d: d[0] * 3),
    _pid(0x0B, "Intake Manifold Pressure", 1, "kPa", lambda d: d[0]),
    _pid(0x0C, "Engine RPM",             2, "rpm", lambda d: (256 * d[0] + d[1]) / 4.0),
    _pid(0x0D, "Vehicle Speed",          1, "km/h", lambda d: d[0]),
    _pid(0x0E, "Timing Advance",         1, "deg", lambda d: d[0] / 2.0 - 64.0),
    _pid(0x0F, "Intake Air Temperature", 1, "degC", lambda d: d[0] - 40),
    _pid(0x10, "MAF Air Flow Rate",      2, "g/s", lambda d: (256 * d[0] + d[1]) / 100.0),
    _pid(0x11, "Throttle Position",      1, "%",   lambda d: d[0] * 100.0 / 255.0),
    _pid(0x14, "O2 Sensor 1 Voltage",    2, "V",   lambda d: d[0] / 200.0),
    _pid(0x1F, "Run Time Since Start",   2, "s",   lambda d: 256 * d[0] + d[1]),
    _pid(0x21, "Distance With MIL On",   2, "km",  lambda d: 256 * d[0] + d[1]),
    _pid(0x23, "Fuel Rail Gauge Pressure", 2, "kPa", lambda d: (256 * d[0] + d[1]) * 10),
    _pid(0x2F, "Fuel Level",             1, "%",   lambda d: d[0] * 100.0 / 255.0),
    _pid(0x33, "Barometric Pressure",    1, "kPa", lambda d: d[0]),
    _pid(0x42, "Control Module Voltage", 2, "V",   lambda d: (256 * d[0] + d[1]) / 1000.0),
    _pid(0x46, "Ambient Air Temperature", 1, "degC", lambda d: d[0] - 40),
    _pid(0x5C, "Engine Oil Temperature", 1, "degC", lambda d: d[0] - 40),
    _pid(0x5E, "Engine Fuel Rate",       2, "L/h", lambda d: (256 * d[0] + d[1]) / 20.0),
    _pid(0x62, "Actual Engine Torque",   1, "%",   lambda d: d[0] - 125),
]}


def decode_pid(pid: int, data: bytes) -> Value | None:
    """Decode the value bytes for ``pid``. Returns None if unknown or too short."""
    spec = PIDS.get(pid)
    if spec is None or len(data) < spec.n_bytes:
        return None
    return spec.decode(data)
