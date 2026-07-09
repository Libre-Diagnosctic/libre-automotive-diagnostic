"""Tests for the DiagnosticSession facade and the hardened rfcomm binding."""
from __future__ import annotations

import adapter.initialization as init
from obd.session import DiagnosticSession
from transport.fake import FakeTransport

VIN = "1HGCM82633A004352"


# --------------------------------------------------------------------------- #
#  DiagnosticSession over the fake transport
# --------------------------------------------------------------------------- #
def test_session_reads_vin_and_dtcs():
    responder = {
        bytes([0x09, 0x02]): bytes([0x49, 0x02, 0x01]) + VIN.encode(),
        bytes([0x03]): bytes([0x43, 0x01, 0x03, 0x01]),  # one DTC: P0301
    }
    with DiagnosticSession(FakeTransport(responder)) as s:
        assert s.read_vin() == VIN
        assert s.read_dtcs() == ["P0301"]


def test_session_scan_live_data():
    responder = {
        bytes([0x01, 0x00]): bytes([0x41, 0x00]) + (1 << (31 - 11)).to_bytes(4, "big"),
        bytes([0x01, 0x0C]): bytes([0x41, 0x0C, 0x1A, 0xF8]),
    }
    with DiagnosticSession.simulated(responder) as s:
        assert s.read_live_data()["Engine RPM"] == "1726 rpm"


# --------------------------------------------------------------------------- #
#  Hardened rfcomm binding (Ticket 8): no shell, validated MAC, password on stdin
# --------------------------------------------------------------------------- #
class _Completed:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def test_binding_refuses_invalid_mac(monkeypatch):
    calls = []
    monkeypatch.setattr(init.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    assert init.run_rfcomm_binding("not-a-mac; rm -rf /", "pw") is False
    assert calls == []  # never shelled out with a bad/injecting MAC


def test_binding_uses_no_shell_and_hides_password(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return _Completed(returncode=0)

    monkeypatch.setattr(init.subprocess, "run", fake_run)
    assert init.run_rfcomm_binding("AA:BB:CC:DD:EE:FF", "s3cret") is True

    assert calls, "expected sudo to be invoked"
    for args, kwargs in calls:
        assert kwargs.get("shell") in (None, False)          # never shell=True
        assert isinstance(args, list)                         # argv, not a string
        assert "s3cret" not in " ".join(args)                 # password not in argv
        assert kwargs.get("input", "").startswith("s3cret")   # password via stdin
        assert args[:2] == ["sudo", "-S"]


def test_binding_reports_failure(monkeypatch):
    monkeypatch.setattr(
        init.subprocess, "run", lambda *a, **k: _Completed(returncode=1, stderr="nope")
    )
    assert init.run_rfcomm_binding("AA:BB:CC:DD:EE:FF", "pw") is False
