"""Tests for the full J1979 mode coverage (modes 02/04/06/07/09/0A + client)."""
from __future__ import annotations

from protocol.obd2 import (
    J1979,
    clear_dtcs,
    describe_dtcs,
    read_calibration_ids,
    read_cvn,
    read_freeze_frame,
    read_monitor_test_results,
    read_pending_dtcs,
    read_permanent_dtcs,
)
from transport.fake import FakeTransport

VIN = "1HGCM82633A004352"


# -- Mode 02 freeze frame ---------------------------------------------------- #
def test_freeze_frame_rpm():
    with FakeTransport({bytes([0x02, 0x0C, 0x00]): bytes([0x42, 0x0C, 0x00, 0x1A, 0xF8])}) as t:
        assert read_freeze_frame(t, 0x0C) == 1726.0


# -- Mode 04 clear ----------------------------------------------------------- #
def test_clear_dtcs_ack():
    with FakeTransport({bytes([0x04]): bytes([0x44])}) as t:
        assert clear_dtcs(t) is True


def test_clear_dtcs_no_ack():
    with FakeTransport({}) as t:
        assert clear_dtcs(t) is False


# -- Modes 07 / 0A pending & permanent DTCs ---------------------------------- #
def test_pending_dtcs():
    with FakeTransport({bytes([0x07]): bytes([0x47, 0x01, 0x03, 0x01])}) as t:
        assert read_pending_dtcs(t) == ["P0301"]


def test_permanent_dtcs():
    with FakeTransport({bytes([0x0A]): bytes([0x4A, 0x01, 0x04, 0x20])}) as t:
        assert read_permanent_dtcs(t) == ["P0420"]


# -- Mode 06 monitor test results -------------------------------------------- #
def test_monitor_test_results():
    rec = bytes([0x01, 0x81, 0x0A, 0x00, 0x64, 0x00, 0x00, 0x01, 0x00])
    with FakeTransport({bytes([0x06, 0x01]): bytes([0x46]) + rec}) as t:
        out = read_monitor_test_results(t, 0x01)
    assert out[0]["obdmid"] == 0x01
    assert out[0]["value"] == 0x64
    assert out[0]["max"] == 0x0100


# -- Mode 09 CALID / CVN ----------------------------------------------------- #
def test_calibration_ids():
    with FakeTransport({bytes([0x09, 0x04]): bytes([0x49, 0x04, 0x01]) + b"CAL0001"}) as t:
        assert read_calibration_ids(t) == "CAL0001"


def test_cvn():
    with FakeTransport({bytes([0x09, 0x06]): bytes([0x49, 0x06, 0x01, 0xDE, 0xAD, 0xBE, 0xEF])}) as t:
        assert read_cvn(t) == "DEADBEEF"


# -- DTC library integration ------------------------------------------------- #
def test_describe_dtcs_attaches_definitions():
    described = describe_dtcs(["P0001"])
    assert described[0]["definition"].startswith("Fuel Volume Regulator")
    assert described[0]["category"] == "Fuel System"


# -- J1979 client bundle ----------------------------------------------------- #
def test_j1979_client():
    responder = {
        bytes([0x09, 0x02]): bytes([0x49, 0x02, 0x01]) + VIN.encode(),
        bytes([0x03]): bytes([0x43, 0x01, 0x03, 0x01]),
        bytes([0x04]): bytes([0x44]),
    }
    with FakeTransport(responder) as t:
        j = J1979(t)
        assert j.vin() == VIN
        assert j.stored_dtcs() == ["P0301"]
        assert j.stored_dtcs(detailed=True)[0]["code"] == "P0301"
        assert j.clear_dtcs() is True
