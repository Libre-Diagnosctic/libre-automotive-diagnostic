"""Tests for the ISO 14229 (UDS) client — request bytes + response parsing."""
from __future__ import annotations

import pytest

from protocol.uds import (
    DtcSettingType,
    NegativeResponseError,
    ResetType,
    Session,
    UDSClient,
    UdsTimeoutError,
    UnexpectedResponseError,
    decode_dtc_status,
    decode_uds_dtc,
)
from transport.fake import FakeTransport


def _client(responder):
    t = FakeTransport(responder)
    t.open()
    return UDSClient(t), t


# --------------------------------------------------------------------------- #
#  Core request/response framing
# --------------------------------------------------------------------------- #
def test_session_control_builds_request_and_parses_timing():
    resp = bytes([0x50, 0x03, 0x00, 0x32, 0x00, 0xC8])  # P2=50ms, P2*=200*10ms
    uds, t = _client({bytes([0x10, 0x03]): resp})
    out = uds.diagnostic_session_control(Session.EXTENDED)
    assert t.sent[-1] == bytes([0x10, 0x03])
    assert out["p2_ms"] == 50
    assert out["p2_star_ms"] == 2000


def test_negative_response_raises_with_nrc_name():
    uds, t = _client({bytes([0x10, 0x02]): bytes([0x7F, 0x10, 0x22])})
    with pytest.raises(NegativeResponseError) as ei:
        uds.diagnostic_session_control(Session.PROGRAMMING)
    assert ei.value.nrc == 0x22
    assert ei.value.nrc_name == "conditionsNotCorrect"


def test_response_pending_is_awaited():
    pending = bytes([0x7F, 0x22, 0x78])
    final = bytes([0x62, 0xF1, 0x90]) + b"WVWZZZ"
    uds, t = _client({bytes([0x22, 0xF1, 0x90]): [pending, final]})
    assert uds.read_data_by_identifier(0xF190) == b"WVWZZZ"


def test_unexpected_sid_raises():
    uds, t = _client({bytes([0x11, 0x01]): bytes([0x62, 0x00])})
    with pytest.raises(UnexpectedResponseError):
        uds.ecu_reset()


def test_no_response_raises_timeout():
    uds, t = _client({})
    with pytest.raises(UdsTimeoutError):
        uds.read_data_by_identifier(0xF190)


# --------------------------------------------------------------------------- #
#  Individual services
# --------------------------------------------------------------------------- #
def test_ecu_reset():
    uds, t = _client({bytes([0x11, 0x01]): bytes([0x51, 0x01])})
    uds.ecu_reset(ResetType.HARD)
    assert t.sent[-1] == bytes([0x11, 0x01])


def test_read_data_by_identifier_strips_did():
    uds, t = _client({bytes([0x22, 0xF1, 0x90]): bytes([0x62, 0xF1, 0x90]) + b"VIN123"})
    assert uds.read_data_by_identifier(0xF190) == b"VIN123"


def test_write_data_by_identifier():
    uds, t = _client({bytes([0x2E, 0xF1, 0x90]) + b"ABC": bytes([0x6E, 0xF1, 0x90])})
    uds.write_data_by_identifier(0xF190, b"ABC")
    assert t.sent[-1] == bytes([0x2E, 0xF1, 0x90]) + b"ABC"


def test_security_access_seed_and_key():
    uds, t = _client({
        bytes([0x27, 0x01]): bytes([0x67, 0x01, 0x11, 0x22, 0x33, 0x44]),
        bytes([0x27, 0x02, 0xAA, 0xBB, 0xCC, 0xDD]): bytes([0x67, 0x02]),
    })
    assert uds.security_access_request_seed(1) == bytes([0x11, 0x22, 0x33, 0x44])
    uds.security_access_send_key(1, bytes([0xAA, 0xBB, 0xCC, 0xDD]))
    assert t.sent[-1] == bytes([0x27, 0x02, 0xAA, 0xBB, 0xCC, 0xDD])


def test_routine_control_start():
    resp = bytes([0x71, 0x01, 0x02, 0x03, 0x00])
    uds, t = _client({bytes([0x31, 0x01, 0x02, 0x03]): resp})
    out = uds.start_routine(0x0203)
    assert t.sent[-1] == bytes([0x31, 0x01, 0x02, 0x03])
    assert out == bytes([0x01, 0x02, 0x03, 0x00])


def test_tester_present_suppressed_sets_bit_and_expects_nothing():
    uds, t = _client({})  # no response configured — must not raise
    uds.tester_present()
    assert t.sent[-1] == bytes([0x3E, 0x80])


def test_control_dtc_setting_off_suppressed():
    uds, t = _client({})
    uds.control_dtc_setting(DtcSettingType.OFF, suppress_response=True)
    assert t.sent[-1] == bytes([0x85, 0x82])


def test_clear_diagnostic_information_default_group():
    uds, t = _client({bytes([0x14, 0xFF, 0xFF, 0xFF]): bytes([0x54])})
    uds.clear_diagnostic_information()
    assert t.sent[-1] == bytes([0x14, 0xFF, 0xFF, 0xFF])


def test_request_download_returns_max_block_length():
    resp = bytes([0x74, 0x20, 0x01, 0x02])
    uds, t = _client({bytes([0x34, 0x00, 0x44, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x02, 0x00]): resp})
    assert uds.request_download(0x1000, 0x200) == 0x0102
    assert t.sent[-1] == bytes([0x34, 0x00, 0x44, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x02, 0x00])


def test_transfer_data_sequence():
    uds, t = _client({bytes([0x36, 0x01]) + b"\xde\xad": bytes([0x76, 0x01])})
    uds.transfer_data(1, b"\xde\xad")
    assert t.sent[-1] == bytes([0x36, 0x01, 0xDE, 0xAD])


def test_read_dtcs_by_status_mask_parses_records():
    resp = bytes([0x59, 0x02, 0xFF, 0x03, 0x01, 0x00, 0x2F, 0x04, 0x20, 0x00, 0x08])
    uds, t = _client({bytes([0x19, 0x02, 0xFF]): resp})
    dtcs = uds.read_dtcs_by_status_mask(0xFF)
    assert t.sent[-1] == bytes([0x19, 0x02, 0xFF])
    assert dtcs[0]["code"] == "P0301-00"
    assert dtcs[0]["status"] == 0x2F
    assert dtcs[0]["flags"]["confirmedDTC"] is True
    assert dtcs[1]["code"] == "P0420-00"


# --------------------------------------------------------------------------- #
#  Decode helpers
# --------------------------------------------------------------------------- #
def test_decode_uds_dtc():
    assert decode_uds_dtc(0x03, 0x01, 0x00) == "P0301-00"
    assert decode_uds_dtc(0xC1, 0x00, 0x12) == "U0100-12"


def test_decode_dtc_status_flags():
    flags = decode_dtc_status(0x2F)
    assert flags["testFailed"] and flags["pendingDTC"] and flags["confirmedDTC"]
    assert flags["warningIndicatorRequested"] is False
