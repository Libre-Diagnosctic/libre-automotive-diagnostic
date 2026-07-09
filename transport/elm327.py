"""ELM327 (serial / Bluetooth rfcomm) transport backend — secondary path.

Wraps a classic ELM327 adapter behind the same :class:`Transport` interface as
SocketCAN, so the protocol layer is identical whether you're on a Raspberry Pi
CAN HAT or a $15 Bluetooth dongle.

Fixes carried over from the old inline ELM code:
  * ``ATSP0`` (automatic protocol) instead of the hardcoded ``ATSP3`` (ISO 9141-2),
    which could not talk to any CAN vehicle (i.e. essentially everything post-2008).
  * headers ON (``ATH1``) so multi-ECU responses can be demuxed and multi-frame
    ISO-TP replies reassembled deterministically.
  * proper ISO-TP reassembly (single / first / consecutive frames) rather than
    scraping a fixed ``43``/``41`` prefix out of one line.

The serial object is injectable (``serial_factory``) so the response parser can
be unit-tested with canned adapter output and no hardware.
"""
from __future__ import annotations

from typing import Callable, Optional

from .base import EcuResponse, Transport, TransportError

# ELM327 power-on + config. Order matters; each returns "OK" (or a banner for ATZ).
_INIT_COMMANDS = (
    "ATZ",    # reset
    "ATE0",   # echo off
    "ATL0",   # linefeeds off
    "ATS0",   # spaces off (compact hex)
    "ATH1",   # headers ON — needed to demux ECUs / reassemble ISO-TP
    "ATSP0",  # AUTO protocol detection (was ATSP3 = ISO 9141-2, CAN-incompatible)
)


class Elm327Transport(Transport):
    """OBD-II over an ELM327 adapter on a serial port.

    Args:
        port:           serial device, e.g. ``/dev/rfcomm0`` or ``COM5``.
        baudrate:       adapter baud (38400 is the common default).
        timeout:        serial read timeout (seconds).
        serial_factory: optional ``(port, baudrate, timeout) -> serial-like``
                        for testing; defaults to :class:`serial.Serial`.
    """

    def __init__(
        self,
        port: str = "/dev/rfcomm0",
        *,
        baudrate: int = 38400,
        timeout: float = 3.0,
        serial_factory: Optional[Callable[..., object]] = None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial_factory = serial_factory
        self._ser = None

    # -- lifecycle -----------------------------------------------------------
    def open(self) -> None:
        if self._serial_factory is not None:
            self._ser = self._serial_factory(self.port, self.baudrate, self.timeout)
        else:  # pragma: no cover - requires pyserial + hardware
            try:
                import serial
            except ImportError as exc:
                raise TransportError("pyserial not installed (pip install pyserial)") from exc
            self._ser = serial.Serial(self.port, baudrate=self.baudrate, timeout=self.timeout)

        for cmd in _INIT_COMMANDS:
            self._send_line(cmd)

    def close(self) -> None:
        if self._ser is not None:
            try:
                close = getattr(self._ser, "close", None)
                if callable(close):
                    close()
            finally:
                self._ser = None

    # -- request/response ----------------------------------------------------
    def request(
        self,
        payload: bytes,
        *,
        functional: bool = True,
        timeout: float = 1.0,
    ) -> list[EcuResponse]:
        if self._ser is None:
            raise TransportError("transport not open — call open() first")
        # ELM327 takes the OBD service+data as ASCII hex; it builds the CAN frame
        # and (for CAN) drives ISO-TP flow control itself. Functional vs physical
        # is handled by the adapter's own addressing.
        raw = self._send_line(payload.hex().upper())
        return _parse_elm_response(raw)

    def receive(self, *, timeout: float = 1.0) -> list[EcuResponse]:
        # The ELM327 collects an ECU's full response (incl. handling 0x78 pending)
        # before returning its prompt, so a follow-up read is normally empty. We
        # still read one more prompt-terminated block in case the buffer has more.
        if self._ser is None:
            raise TransportError("transport not open — call open() first")
        try:
            data = self._ser.read_until(b">").decode("ascii", errors="ignore")
        except Exception:  # pragma: no cover - serial timeout/close
            return []
        return _parse_elm_response(data)

    # -- serial helpers ------------------------------------------------------
    def _send_line(self, command: str) -> str:
        self._ser.write((command + "\r").encode("ascii"))
        data = self._ser.read_until(b">")
        return data.decode("ascii", errors="ignore")


# --------------------------------------------------------------------------- #
#  ELM327 response parsing + ISO-TP reassembly
# --------------------------------------------------------------------------- #
def _parse_elm_response(raw: str) -> list[EcuResponse]:
    """Parse a (possibly multi-line, multi-ECU) ELM327 CAN response.

    With headers on and spaces off, each line is one CAN frame as continuous hex:
    a 3-nibble 11-bit source id followed by the ISO-TP frame bytes. Frames are
    grouped by source id and reassembled per ECU.
    """
    frames_by_source: dict[int, list[bytes]] = {}
    order: list[int] = []

    for line in raw.replace("\r", "\n").split("\n"):
        line = line.strip().replace(" ", "").upper()
        if not line or line == ">":
            continue
        if any(tok in line for tok in ("SEARCHING", "NODATA", "STOPPED", "ERROR", "UNABLE", "?")):
            continue
        if len(line) < 4 or not _is_hex(line):
            continue
        src = int(line[0:3], 16)          # 11-bit CAN id (3 hex nibbles)
        try:
            frame = bytes.fromhex(line[3:])
        except ValueError:
            continue
        if not frame:
            continue
        if src not in frames_by_source:
            frames_by_source[src] = []
            order.append(src)
        frames_by_source[src].append(frame)

    responses: list[EcuResponse] = []
    for src in order:
        data = _reassemble_isotp(frames_by_source[src])
        if data:
            responses.append(EcuResponse(source=src, data=data))
    return responses


def _reassemble_isotp(frames: list[bytes]) -> bytes:
    """Reassemble ISO 15765-2 frames from one ECU into the service payload."""
    if not frames:
        return b""

    pci_type = frames[0][0] >> 4
    if pci_type == 0x0:  # Single Frame: 0L <data...>
        length = frames[0][0] & 0x0F
        return frames[0][1 : 1 + length]

    if pci_type == 0x1:  # First Frame: 1LLL <6 data...> then Consecutive Frames
        length = ((frames[0][0] & 0x0F) << 8) | frames[0][1]
        data = bytearray(frames[0][2:])
        for f in frames[1:]:
            if f and (f[0] >> 4) == 0x2:  # Consecutive Frame: 2N <7 data...>
                data += f[1:]
        return bytes(data[:length])

    # Unexpected leading frame type — return raw as a best effort.
    return frames[0]


def _is_hex(s: str) -> bool:
    return all(c in "0123456789ABCDEF" for c in s)
