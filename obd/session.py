"""Backend-neutral diagnostic session — the single seam the GUI talks to.

Wraps a :class:`~transport.base.Transport` plus the OBD-II protocol layer so the
UI calls ``session.read_live_data()`` / ``read_dtcs()`` / ``read_vin()`` without
caring whether it's SocketCAN, ELM327, or the in-memory fake underneath.

    with DiagnosticSession.socketcan("can0") as s:
        print(s.read_vin(), s.read_dtcs(), s.read_live_data())
"""
from __future__ import annotations

from protocol import obd2
from transport.base import Transport


class DiagnosticSession:
    """A high-level diagnostic API over one transport backend."""

    def __init__(self, transport: Transport, *, make: str | None = None):
        self._t = transport
        self.make = make
        self._open = False

    # -- lifecycle -----------------------------------------------------------
    def open(self) -> "DiagnosticSession":
        if not self._open:
            self._t.open()
            self._open = True
        return self

    def close(self) -> None:
        if self._open:
            self._t.close()
            self._open = False

    def __enter__(self) -> "DiagnosticSession":
        return self.open()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- diagnostics ---------------------------------------------------------
    def read_vin(self) -> str | None:
        return obd2.read_vin(self._t)

    def read_live_data(self) -> dict[str, str]:
        """Return ``{PID name: "value unit"}`` for every supported, known PID."""
        return obd2.scan_live_data(self._t)

    def read_dtcs(self, *, detailed: bool = False):
        """Stored DTCs (Mode 03). With detailed=True, attach library definitions."""
        codes = obd2.read_dtcs(self._t)
        return obd2.describe_dtcs(codes, self.make) if detailed else codes

    # -- subsystem clients ---------------------------------------------------
    def j1979(self):
        """Full SAE J1979 OBD-II client (all 10 modes) over this transport."""
        return obd2.J1979(self._t, make=self.make)

    def uds(self):
        """Full ISO 14229 UDS client over this transport."""
        from protocol.uds import UDSClient

        return UDSClient(self._t)

    # -- factories -----------------------------------------------------------
    @classmethod
    def socketcan(cls, channel: str = "can0", **kwargs) -> "DiagnosticSession":
        from transport.socketcan import SocketCanTransport

        return cls(SocketCanTransport(channel, **kwargs))

    @classmethod
    def elm327(cls, port: str = "/dev/rfcomm0", **kwargs) -> "DiagnosticSession":
        from transport.elm327 import Elm327Transport

        return cls(Elm327Transport(port, **kwargs))

    @classmethod
    def simulated(cls, responder=None) -> "DiagnosticSession":
        """A fully offline session (for GUI dev / demos with no vehicle)."""
        from transport.fake import FakeTransport

        return cls(FakeTransport(responder if responder is not None else {}))
