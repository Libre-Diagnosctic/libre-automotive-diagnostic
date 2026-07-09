"""Tests for the Ford CAN GDS (2003-era KWP2000-over-CAN) profile.

Ford GDS reuses the authoritative KWP2000 service layer, so these tests focus on
the Ford-specific glue: the module address map and that FordGDS builds the right
KWP2000 request bytes and parses canned responses (VIN + a generic DID).
"""
from __future__ import annotations

import pytest

from protocol.ford_gds import (
    FORD_DID_CALIBRATION_LEVEL,
    FORD_DID_VIN,
    FordGDS,
    FordModule,
)
from protocol.kwp2000 import KwpNegativeResponseError
from transport.base import EcuResponse
from transport.fake import FakeTransport


def _gds(responder, module=FordModule.PCM):
    t = FakeTransport(responder)
    t.open()
    return FordGDS(t, module=module), t


# --------------------------------------------------------------------------- #
#  Address map
# --------------------------------------------------------------------------- #
def test_pcm_addressing_is_authoritative():
    assert FordModule.PCM.request_id == 0x7E0
    assert FordModule.PCM.response_id == 0x7E8
    assert FordModule.PCM.authoritative is True
    assert FordModule.PCM.is_inferred is False


def test_tcm_addressing_is_authoritative():
    assert FordModule.TCM.request_id == 0x7E1
    assert FordModule.TCM.response_id == 0x7E9
    assert FordModule.TCM.authoritative is True


def test_body_modules_are_marked_inferred():
    for m in (FordModule.ABS, FordModule.RCM, FordModule.IPC,
              FordModule.BCM, FordModule.PAM):
        assert m.is_inferred is True, f"{m.name} should be inferred"


def test_gds_binds_module_addressing():
    gds, _ = _gds({}, module=FordModule.TCM)
    assert gds.request_id == 0x7E1
    assert gds.response_id == 0x7E9


# --------------------------------------------------------------------------- #
#  Session
# --------------------------------------------------------------------------- #
def test_enter_extended_session_builds_request():
    gds, t = _gds({bytes([0x10, 0x92]): bytes([0x50, 0x92])})
    gds.enter_extended_session()
    assert t.sent[-1] == bytes([0x10, 0x92])


# --------------------------------------------------------------------------- #
#  VIN read (DID 0xF190) against a canned response
# --------------------------------------------------------------------------- #
def test_read_vin_decodes_ascii():
    vin = b"1FTFW1ET5DFC12345"  # 17-char Ford VIN
    resp = bytes([0x62, 0xF1, 0x90]) + vin
    gds, t = _gds({bytes([0x22, 0xF1, 0x90]): resp})
    assert gds.read_vin() == "1FTFW1ET5DFC12345"
    assert t.sent[-1] == bytes([0x22, 0xF1, 0x90])
    assert FORD_DID_VIN == 0xF190


def test_read_vin_strips_null_padding():
    vin = b"1FTFW1ET5DFC12345" + b"\x00\x00\x00"
    resp = bytes([0x62, 0xF1, 0x90]) + vin
    gds, _ = _gds({bytes([0x22, 0xF1, 0x90]): resp})
    assert gds.read_vin() == "1FTFW1ET5DFC12345"


def test_read_vin_from_response_source_address():
    """VIN read works when the fake replies from the PCM's own 0x7E8 source."""
    vin = b"1FTFW1ET5DFC12345"
    resp = EcuResponse(0x7E8, bytes([0x62, 0xF1, 0x90]) + vin)
    gds, _ = _gds({bytes([0x22, 0xF1, 0x90]): resp})
    assert gds.read_vin() == "1FTFW1ET5DFC12345"


# --------------------------------------------------------------------------- #
#  Generic DID read + calibration level
# --------------------------------------------------------------------------- #
def test_read_data_by_identifier_strips_did():
    resp = bytes([0x62, 0xF1, 0x11]) + b"AA5A-14C204-BC"
    gds, t = _gds({bytes([0x22, 0xF1, 0x11]): resp})
    assert gds.read_data_by_identifier(0xF111) == b"AA5A-14C204-BC"
    assert t.sent[-1] == bytes([0x22, 0xF1, 0x11])


def test_read_calibration_level_decodes():
    cal = b"DFC-AB12"
    resp = bytes([0x62, 0xF1, 0x24]) + cal
    gds, t = _gds({bytes([0x22, 0xF1, 0x24]): resp})
    assert gds.read_calibration_level() == "DFC-AB12"
    assert t.sent[-1] == bytes([0x22, 0xF1, 0x24])
    assert FORD_DID_CALIBRATION_LEVEL == 0xF124


def test_read_part_number_default_did():
    resp = bytes([0x62, 0xF1, 0x11]) + b"1234"
    gds, t = _gds({bytes([0x22, 0xF1, 0x11]): resp})
    assert gds.read_part_number() == "1234"
    assert t.sent[-1] == bytes([0x22, 0xF1, 0x11])


# --------------------------------------------------------------------------- #
#  Local identifier read
# --------------------------------------------------------------------------- #
def test_read_data_by_local_identifier():
    resp = bytes([0x61, 0x01]) + b"\xde\xad\xbe\xef"
    gds, t = _gds({bytes([0x21, 0x01]): resp})
    assert gds.read_data_by_local_identifier(0x01) == b"\xde\xad\xbe\xef"
    assert t.sent[-1] == bytes([0x21, 0x01])


# --------------------------------------------------------------------------- #
#  DTCs
# --------------------------------------------------------------------------- #
def test_read_dtcs_parses_records():
    # 58 <count=2> [03 01 2F] [04 20 08]
    resp = bytes([0x58, 0x02, 0x03, 0x01, 0x2F, 0x04, 0x20, 0x08])
    gds, t = _gds({bytes([0x18, 0x00, 0xFF, 0x00]): resp})
    dtcs = gds.read_dtcs()
    assert t.sent[-1] == bytes([0x18, 0x00, 0xFF, 0x00])
    assert dtcs[0]["code"] == "P0301"
    assert dtcs[1]["code"] == "P0420"


def test_clear_dtcs_builds_request():
    gds, t = _gds({bytes([0x14, 0xFF, 0x00]): bytes([0x54])})
    gds.clear_dtcs()
    assert t.sent[-1] == bytes([0x14, 0xFF, 0x00])


# --------------------------------------------------------------------------- #
#  Security access (seed only — Ford key algo is proprietary)
# --------------------------------------------------------------------------- #
def test_security_access_returns_seed():
    resp = bytes([0x67, 0x01, 0x11, 0x22, 0x33, 0x44])
    gds, t = _gds({bytes([0x27, 0x01]): resp})
    assert gds.security_access(0x01) == bytes([0x11, 0x22, 0x33, 0x44])
    assert t.sent[-1] == bytes([0x27, 0x01])


def test_security_access_send_key():
    responder = {
        bytes([0x27, 0x01]): bytes([0x67, 0x01, 0x11, 0x22, 0x33, 0x44]),
        bytes([0x27, 0x02, 0xAA, 0xBB, 0xCC, 0xDD]): bytes([0x67, 0x02]),
    }
    gds, t = _gds(responder)
    gds.security_access_request_seed(1)
    gds.security_access_send_key(1, bytes([0xAA, 0xBB, 0xCC, 0xDD]))
    assert t.sent[-1] == bytes([0x27, 0x02, 0xAA, 0xBB, 0xCC, 0xDD])


# --------------------------------------------------------------------------- #
#  Tester present + error propagation
# --------------------------------------------------------------------------- #
def test_tester_present_no_response_required():
    gds, t = _gds({})
    gds.tester_present()
    assert t.sent[-1] == bytes([0x3E, 0x02])


def test_negative_response_propagates():
    gds, _ = _gds({bytes([0x22, 0xF1, 0x24]): bytes([0x7F, 0x22, 0x31])})
    with pytest.raises(KwpNegativeResponseError) as ei:
        gds.read_calibration_level()
    assert ei.value.nrc == 0x31
