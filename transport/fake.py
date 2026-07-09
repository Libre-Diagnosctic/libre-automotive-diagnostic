"""In-memory transport for tests and hardware-free GUI development.

Runs on any platform (no CAN, no serial, no kernel modules). Feed it either a
mapping of request-bytes -> response, or a callable that returns a list of
:class:`EcuResponse`.

Response values in a mapping may be:
  * ``bytes``                 -> one reply from ECU 0x7E8
  * ``list[bytes]``           -> the first is returned by :meth:`request`, the rest
                                 are queued for :meth:`receive` (models UDS 0x78)
  * ``list[EcuResponse]``     -> returned as-is by :meth:`request`

Sent payloads are recorded in ``.sent`` so tests can assert the exact request bytes.
"""
from __future__ import annotations

from typing import Callable, Mapping, Union

from .base import EcuResponse, Transport, TransportError

Responder = Union[
    Mapping[bytes, object],
    Callable[[bytes], "list[EcuResponse]"],
]


def _as_responses(value) -> list[EcuResponse]:
    if value is None:
        return []
    if isinstance(value, EcuResponse):
        return [value]
    if isinstance(value, (bytes, bytearray)):
        return [EcuResponse(0x7E8, bytes(value))]
    out: list[EcuResponse] = []
    for item in value:  # list/tuple of bytes or EcuResponse
        out.extend(_as_responses(item))
    return out


class FakeTransport(Transport):
    """A Transport backed by a dict or a function instead of hardware."""

    def __init__(self, responder: Responder):
        self._responder = responder
        self._open = False
        self.sent: list[bytes] = []
        self._followups: list[EcuResponse] = []

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def request(
        self,
        payload: bytes,
        *,
        functional: bool = True,
        timeout: float = 1.0,
    ) -> list[EcuResponse]:
        if not self._open:
            raise TransportError("transport not open — call open() first")

        payload = bytes(payload)
        self.sent.append(payload)
        self._followups = []

        if callable(self._responder):
            return list(self._responder(payload))

        responses = _as_responses(self._responder.get(payload))
        if len(responses) > 1:
            # First delivered now; the rest are available via receive() (0x78 flow).
            self._followups = responses[1:]
            return responses[:1]
        return responses

    def receive(self, *, timeout: float = 1.0) -> list[EcuResponse]:
        if not self._followups:
            return []
        return [self._followups.pop(0)]
