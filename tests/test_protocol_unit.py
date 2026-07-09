"""Protocol-layer unit tests — no hardware, run on any platform (incl. Windows CI).

These drive the OBD-II helpers through :class:`FakeTransport`, so they verify the
parsing/decoding logic without needing SocketCAN. The end-to-end SocketCAN path is
covered separately in ``test_socketcan_vin.py`` (Linux only).
"""
from __future__ import annotations

import pytest

from protocol.dtc import decode_dtc, encode_dtc
from protocol.obd2 import (
    read_coolant_temp,
    read_dtcs,
    read_engine_rpm,
    read_pid,
    read_supported_pids,
    read_vehicle_speed,
    read_vin,
    scan_live_data,
)
from protocol.pids import PIDS, decode_pid
from transport.fake import FakeTransport


# --------------------------------------------------------------------------- #
#  DTC codec
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code, wire",
    [
        ("P0301", b"\x03\x01"),
        ("P0420", b"\x04\x20"),
        ("P1234", b"\x12\x34"),
        ("C1234", b"\x52\x34"),
        ("B0001", b"\x80\x01"),
        ("U0100", b"\xc1\x00"),
    ],
)
def test_dtc_encode_matches_wire(code, wire):
    assert encode_dtc(code) == wire


@pytest.mark.parametrize(
    "code", ["P0301", "P0420", "P1234", "C1234", "B0001", "U0100", "P0000"]
)
def test_dtc_roundtrip(code):
    hi, lo = encode_dtc(code)
    assert decode_dtc(hi, lo) == code


# --------------------------------------------------------------------------- #
#  Mode 09 VIN
# --------------------------------------------------------------------------- #
def test_read_vin():
    vin = "1HGCM82633A004352"
    responder = {bytes([0x09, 0x02]): bytes([0x49, 0x02, 0x01]) + vin.encode()}
    with FakeTransport(responder) as t:
        assert read_vin(t) == vin


def test_read_vin_no_response():
    with FakeTransport({}) as t:
        assert read_vin(t) is None


# --------------------------------------------------------------------------- #
#  Mode 03 DTCs
# --------------------------------------------------------------------------- #
def test_read_dtcs():
    body = bytes([0x43, 0x02]) + encode_dtc("P0301") + encode_dtc("P0420")
    with FakeTransport({bytes([0x03]): body}) as t:
        assert read_dtcs(t) == ["P0301", "P0420"]


def test_read_dtcs_none_stored():
    with FakeTransport({bytes([0x03]): bytes([0x43, 0x00])}) as t:
        assert read_dtcs(t) == []


# --------------------------------------------------------------------------- #
#  Mode 01 live PIDs
# --------------------------------------------------------------------------- #
def test_read_engine_rpm():
    with FakeTransport({bytes([0x01, 0x0C]): bytes([0x41, 0x0C, 0x1A, 0xF8])}) as t:
        assert read_engine_rpm(t) == 1726.0


def test_read_vehicle_speed():
    with FakeTransport({bytes([0x01, 0x0D]): bytes([0x41, 0x0D, 0x50])}) as t:
        assert read_vehicle_speed(t) == 80


def test_read_coolant_temp():
    with FakeTransport({bytes([0x01, 0x05]): bytes([0x41, 0x05, 0x5A])}) as t:
        assert read_coolant_temp(t) == 50


# --------------------------------------------------------------------------- #
#  J1979 PID table (formulas ported from obd_formulas.c)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "pid, data, expected",
    [
        (0x04, b"\x7f", 127 * 100 / 255),    # engine load %
        (0x05, b"\x5a", 50),                  # coolant temp degC
        (0x06, b"\x80", 0.0),                 # fuel trim % (0x80 -> 0)
        (0x0A, b"\x64", 300),                 # fuel pressure kPa (100*3)
        (0x0C, b"\x1a\xf8", 1726.0),          # rpm
        (0x0D, b"\x50", 80),                  # speed km/h
        (0x0E, b"\x80", 0.0),                 # timing advance deg (128/2-64)
        (0x10, b"\x0a\x00", 25.6),            # MAF g/s (2560/100)
        (0x11, b"\xff", 100.0),               # throttle % (255*100/255)
        (0x42, b"\x2f\xda", 12.250),          # module voltage V (12250/1000)
        (0x62, b"\x7d", 0),                   # torque % (125-125)
    ],
)
def test_pid_formulas(pid, data, expected):
    assert decode_pid(pid, data) == pytest.approx(expected)


def test_read_pid_via_transport():
    with FakeTransport({bytes([0x01, 0x0C]): bytes([0x41, 0x0C, 0x1A, 0xF8])}) as t:
        assert read_pid(t, 0x0C) == 1726.0


def test_read_supported_pids():
    # Advertise PIDs 0x0C and 0x0D supported, no further range.
    bits = (1 << (31 - 11)) | (1 << (31 - 12))  # PID 0x0C (i=11), 0x0D (i=12)
    resp = bytes([0x41, 0x00]) + bits.to_bytes(4, "big")
    with FakeTransport({bytes([0x01, 0x00]): resp}) as t:
        assert read_supported_pids(t) == {0x0C, 0x0D}


def test_scan_live_data():
    responder = {
        bytes([0x01, 0x00]): bytes([0x41, 0x00])
        + ((1 << (31 - 11)) | (1 << (31 - 4))).to_bytes(4, "big"),  # PID 0x0C, 0x05
        bytes([0x01, 0x0C]): bytes([0x41, 0x0C, 0x1A, 0xF8]),
        bytes([0x01, 0x05]): bytes([0x41, 0x05, 0x5A]),
    }
    with FakeTransport(responder) as t:
        data = scan_live_data(t)
    assert data["Engine RPM"] == "1726 rpm"
    assert data["Coolant Temperature"] == "50 degC"


def test_every_pid_decodes_without_error():
    # Each decoder must handle a full-length input without raising.
    for pid, spec in PIDS.items():
        assert decode_pid(pid, b"\x00" * spec.n_bytes) is not None
