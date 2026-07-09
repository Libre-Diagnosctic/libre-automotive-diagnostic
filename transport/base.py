"""Transport abstraction: one interface, many backends.

A ``Transport`` carries OBD-II / UDS *service payloads* to the vehicle and returns
the responses from every ECU that answered. Each backend (SocketCAN, ELM327, an
in-memory fake, ...) hides all framing — ISO-TP segmentation, ELM327 ASCII echo,
flow control — so the protocol layer above never touches a raw CAN frame.

This is the seam that lets SocketCAN be the first-class backend while ELM327
stays alive as a secondary one, both feeding a single OBD-II/UDS service layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TransportError(Exception):
    """A backend could not open, send, or receive."""


@dataclass(frozen=True)
class EcuResponse:
    """One ECU's reply to a request.

    Attributes:
        source: responding address, e.g. ``0x7E8``..``0x7EF`` for 11-bit OBD-II.
        data:   the reassembled service response bytes, e.g.
                ``b"\\x49\\x02\\x01..."`` for a Mode 09 VIN reply.
    """

    source: int
    data: bytes

    @property
    def service(self) -> int:
        """Response service id (request SID + 0x40), or -1 if empty."""
        return self.data[0] if self.data else -1

    @property
    def is_negative(self) -> bool:
        """True for a negative response (``0x7F <sid> <nrc>``)."""
        return len(self.data) >= 1 and self.data[0] == 0x7F


class Transport(ABC):
    """Backend-neutral request/response channel to a vehicle."""

    @abstractmethod
    def open(self) -> None:
        """Acquire the underlying interface. Raise ``TransportError`` on failure."""

    @abstractmethod
    def close(self) -> None:
        """Release the interface. Safe to call even if never opened."""

    @abstractmethod
    def request(
        self,
        payload: bytes,
        *,
        functional: bool = True,
        timeout: float = 1.0,
    ) -> list[EcuResponse]:
        """Send one request and collect responses.

        Args:
            payload:    raw service bytes, e.g. ``b"\\x09\\x02"`` (Mode 09 PID 02, VIN).
            functional: broadcast to all ECUs and gather every reply within
                        ``timeout`` (True) vs. address a single ECU (False).
            timeout:    seconds to wait for (further) responses.

        Returns:
            A possibly-empty list of :class:`EcuResponse`. An empty list means
            the vehicle did not answer — this is *not* an error and must not raise.
        """

    def receive(self, *, timeout: float = 1.0) -> list[EcuResponse]:
        """Read a further response without sending anything.

        Needed for UDS response-pending (NRC 0x78): after a request the ECU may
        send ``7F <sid> 78`` and then the real answer, which must be read without
        re-sending. Backends that cannot support this return an empty list.
        """
        return []

    # -- context-manager sugar: ``with SomeTransport(...) as t:`` --------------
    def __enter__(self) -> "Transport":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
