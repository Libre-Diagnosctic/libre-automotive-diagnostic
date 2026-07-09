"""ELM327 backend tests — canned adapter output through a fake serial port.

No hardware and no pyserial needed: a fake serial injects recorded ELM327
responses, so the ISO-TP-over-ELM reassembly and multi-ECU demux are verified
directly. Runs on any platform.
"""
from __future__ import annotations

from protocol.obd2 import read_dtcs, read_vin
from transport.elm327 import Elm327Transport, _parse_elm_response


class FakeSerial:
    """Minimal serial stand-in: returns canned bytes for each written command."""

    def __init__(self, responses: dict[str, bytes]):
        self.responses = responses
        self.written: list[str] = []
        self._last = ""

    def write(self, data: bytes) -> int:
        self._last = data.decode("ascii").strip()
        self.written.append(self._last)
        return len(data)

    def read_until(self, expected: bytes = b">") -> bytes:
        # Init commands (ATZ/ATE0/...) get a generic OK; requests get their data.
        return self.responses.get(self._last, b"OK\r>")

    def close(self) -> None:
        pass


def _transport(responses: dict[str, bytes]) -> Elm327Transport:
    return Elm327Transport("test", serial_factory=lambda *a: FakeSerial(responses))


# --------------------------------------------------------------------------- #
#  ISO-TP reassembly over ELM327 (headers on, spaces off)
# --------------------------------------------------------------------------- #
def test_vin_multiframe_reassembly():
    # Mode 09 PID 02 VIN reply from ECU 7E8, spread over 3 ISO-TP frames.
    vin_resp = b"\r".join([
        b"7E81014490201314847",   # First Frame:  10 14 | 49 02 01 31 48 47
        b"7E821434D3832363333",   # Consecutive:  21 | 43 4D 38 32 36 33 33
        b"7E82241303034333532",   # Consecutive:  22 | 41 30 30 34 33 35 32
        b">",
    ])
    with _transport({"0902": vin_resp}) as t:
        assert read_vin(t) == "1HGCM82633A004352"


def test_dtc_single_frame():
    # Mode 03 reply: single frame 06 43 02 0301 0420 -> P0301, P0420.
    dtc_resp = b"7E806430203010420\r>"
    with _transport({"03": dtc_resp}) as t:
        assert read_dtcs(t) == ["P0301", "P0420"]


def test_multi_ecu_demux():
    # Two ECUs answer 0100; each is a separate EcuResponse.
    # Single frame per ECU: 06 41 00 00 00 00 00  (src + 14 hex nibbles).
    raw = "7E806410000000000\r7E906410000000000\r>"
    responses = _parse_elm_response(raw)
    assert {r.source for r in responses} == {0x7E8, 0x7E9}


def test_noise_lines_ignored():
    raw = "SEARCHING...\rNO DATA\r>"
    assert _parse_elm_response(raw) == []


def test_init_uses_auto_protocol():
    # Regression guard: the init sequence must use ATSP0 (auto), never ATSP3.
    fake = FakeSerial({})
    t = Elm327Transport("test", serial_factory=lambda *a: fake)
    t.open()
    assert "ATSP0" in fake.written
    assert "ATSP3" not in fake.written
    assert "ATH1" in fake.written  # headers on, needed for demux/reassembly
