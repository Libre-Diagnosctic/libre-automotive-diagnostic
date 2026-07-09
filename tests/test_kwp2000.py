"""Tests for the ISO 14230-3 (KWP2000) client — request bytes + response parsing."""
from __future__ import annotations

import pytest

from protocol.kwp2000 import (
    KWP2000Client,
    KwpNegativeResponseError,
    KwpTimeoutError,
    Session,
    UnexpectedResponseError,
    decode_dtc_status,
)
from transport.fake import FakeTransport


def _client(responder):
    t = FakeTransport(responder)
    t.open()
    return KWP2000Client(t), t


# --------------------------------------------------------------------------- #
#  Session control
# --------------------------------------------------------------------------- #
def test_start_diagnostic_session_builds_request():
    kwp, t = _client({bytes([0x10, 0x92]): bytes([0x50, 0x92])})
    kwp.start_diagnostic_session(Session.EXTENDED)
    assert t.sent[-1] == bytes([0x10, 0x92])


def test_start_diagnostic_session_default_is_0x81():
    kwp, t = _client({bytes([0x10, 0x81]): bytes([0x50, 0x81])})
    kwp.start_diagnostic_session()
    assert t.sent[-1] == bytes([0x10, 0x81])


def test_stop_diagnostic_session():
    kwp, t = _client({bytes([0x20]): bytes([0x60])})
    kwp.stop_diagnostic_session()
    assert t.sent[-1] == bytes([0x20])


def test_ecu_reset():
    kwp, t = _client({bytes([0x11, 0x01]): bytes([0x51, 0x01])})
    kwp.ecu_reset()
    assert t.sent[-1] == bytes([0x11, 0x01])


# --------------------------------------------------------------------------- #
#  Read data (RDBI / RDLI / ECU identification)
# --------------------------------------------------------------------------- #
def test_read_data_by_common_identifier_strips_did():
    kwp, t = _client({bytes([0x22, 0xF1, 0x90]): bytes([0x62, 0xF1, 0x90]) + b"VIN123"})
    assert kwp.read_data_by_common_identifier(0xF190) == b"VIN123"
    assert t.sent[-1] == bytes([0x22, 0xF1, 0x90])


def test_read_data_by_local_identifier_strips_lid():
    kwp, t = _client({bytes([0x21, 0x01]): bytes([0x61, 0x01]) + b"\xde\xad\xbe\xef"})
    assert kwp.read_data_by_local_identifier(0x01) == b"\xde\xad\xbe\xef"
    assert t.sent[-1] == bytes([0x21, 0x01])


def test_read_ecu_identification_strips_option():
    kwp, t = _client({bytes([0x1A, 0x80]): bytes([0x5A, 0x80]) + b"ECU-ID"})
    assert kwp.read_ecu_identification(0x80) == b"ECU-ID"
    assert t.sent[-1] == bytes([0x1A, 0x80])


def test_write_data_by_local_identifier():
    kwp, t = _client({bytes([0x3B, 0x05]) + b"ABC": bytes([0x7B, 0x05])})
    kwp.write_data_by_local_identifier(0x05, b"ABC")
    assert t.sent[-1] == bytes([0x3B, 0x05]) + b"ABC"


# --------------------------------------------------------------------------- #
#  Security access
# --------------------------------------------------------------------------- #
def test_security_access_seed_and_key():
    kwp, t = _client({
        bytes([0x27, 0x01]): bytes([0x67, 0x01, 0x11, 0x22, 0x33, 0x44]),
        bytes([0x27, 0x02, 0xAA, 0xBB, 0xCC, 0xDD]): bytes([0x67, 0x02]),
    })
    assert kwp.security_access_request_seed(1) == bytes([0x11, 0x22, 0x33, 0x44])
    kwp.security_access_send_key(1, bytes([0xAA, 0xBB, 0xCC, 0xDD]))
    assert t.sent[-1] == bytes([0x27, 0x02, 0xAA, 0xBB, 0xCC, 0xDD])


# --------------------------------------------------------------------------- #
#  DTC read (0x18) — 3-byte records: DTC hi, lo, statusOfDTC
# --------------------------------------------------------------------------- #
def test_read_dtcs_by_status_parses_3byte_records():
    # 58 <count=2> [03 01 2F] [04 20 08]
    resp = bytes([0x58, 0x02, 0x03, 0x01, 0x2F, 0x04, 0x20, 0x08])
    kwp, t = _client({bytes([0x18, 0x00, 0xFF, 0x00]): resp})
    dtcs = kwp.read_dtcs_by_status(0x00, 0xFF00)
    assert t.sent[-1] == bytes([0x18, 0x00, 0xFF, 0x00])
    assert dtcs[0]["code"] == "P0301"
    assert dtcs[0]["status"] == 0x2F
    assert dtcs[0]["flags"]["confirmedDTC"] is True
    assert dtcs[1]["code"] == "P0420"


def test_read_status_of_dtc():
    resp = bytes([0x57, 0x03, 0x01, 0x2F])
    kwp, t = _client({bytes([0x17, 0x03, 0x01]): resp})
    dtcs = kwp.read_status_of_dtc(0x0301)
    assert t.sent[-1] == bytes([0x17, 0x03, 0x01])
    assert dtcs[0]["code"] == "P0301"
    assert dtcs[0]["status"] == 0x2F


def test_clear_diagnostic_information_default_group():
    kwp, t = _client({bytes([0x14, 0xFF, 0x00]): bytes([0x54])})
    kwp.clear_diagnostic_information()
    assert t.sent[-1] == bytes([0x14, 0xFF, 0x00])


# --------------------------------------------------------------------------- #
#  Routines
# --------------------------------------------------------------------------- #
def test_start_routine_by_local_identifier():
    kwp, t = _client({bytes([0x31, 0x02, 0xAA]): bytes([0x71, 0x02, 0x00, 0x01])})
    out = kwp.start_routine_by_local_identifier(0x02, b"\xaa")
    assert t.sent[-1] == bytes([0x31, 0x02, 0xAA])
    assert out == bytes([0x00, 0x01])


def test_request_routine_results():
    kwp, t = _client({bytes([0x33, 0x02]): bytes([0x73, 0x02, 0xDE, 0xAD])})
    assert kwp.request_routine_results_by_local_identifier(0x02) == bytes([0xDE, 0xAD])


# --------------------------------------------------------------------------- #
#  TesterPresent — KWP has no suppress bit, uses response-required byte
# --------------------------------------------------------------------------- #
def test_tester_present_no_response_required():
    kwp, t = _client({})  # no response configured — must not raise
    kwp.tester_present()
    assert t.sent[-1] == bytes([0x3E, 0x02])


def test_tester_present_response_required():
    kwp, t = _client({bytes([0x3E, 0x01]): bytes([0x7E, 0x01])})
    kwp.tester_present(response_required=True)
    assert t.sent[-1] == bytes([0x3E, 0x01])


# --------------------------------------------------------------------------- #
#  Error handling
# --------------------------------------------------------------------------- #
def test_negative_response_raises_with_nrc_name():
    kwp, t = _client({bytes([0x10, 0x85]): bytes([0x7F, 0x10, 0x22])})
    with pytest.raises(KwpNegativeResponseError) as ei:
        kwp.start_diagnostic_session(Session.PROGRAMMING)
    assert ei.value.nrc == 0x22
    assert ei.value.nrc_name == "conditionsNotCorrect"


def test_response_pending_is_awaited():
    pending = bytes([0x7F, 0x22, 0x78])
    final = bytes([0x62, 0xF1, 0x90]) + b"WVWZZZ"
    kwp, t = _client({bytes([0x22, 0xF1, 0x90]): [pending, final]})
    assert kwp.read_data_by_common_identifier(0xF190) == b"WVWZZZ"


def test_unexpected_sid_raises():
    kwp, t = _client({bytes([0x11, 0x01]): bytes([0x62, 0x00])})
    with pytest.raises(UnexpectedResponseError):
        kwp.ecu_reset()


def test_no_response_raises_timeout():
    kwp, t = _client({})
    with pytest.raises(KwpTimeoutError):
        kwp.read_data_by_common_identifier(0xF190)


def test_decode_dtc_status_flags():
    flags = decode_dtc_status(0x2F)
    assert flags["testFailed"] and flags["pendingDTC"] and flags["confirmedDTC"]
    assert flags["warningIndicatorRequested"] is False
