"""SocketCAN + kernel ISO-TP (ISO 15765-2) transport backend.

Linux only. Requires:
  * the ``can_isotp`` kernel module  (``sudo modprobe can_isotp``)
  * the ``can-isotp`` Python package (``pip install can-isotp``)

The whole point of this backend: **the kernel does ISO-TP for you.** First
Frame / Consecutive Frame / Flow Control / block size / STmin are handled in the
``can_isotp`` module, so a multi-frame reply (VIN, long DTC lists, UDS DIDs)
arrives as a single reassembled payload. This is exactly what the old hand-rolled
``custom_isotp.h`` in the C tree never got right.

Addressing follows ISO 15765-4 for legislated OBD-II on CAN:

    tester -> ECU n (physical request / flow control) : 0x7E0 + n
    ECU n  -> tester (physical response)              : 0x7E8 + n
    tester -> all ECUs (functional broadcast)         : 0x7DF

This backend currently opens a *physical* ISO-TP channel to one ECU (default
ECU 0 -> 0x7E0/0x7E8), which handles multi-frame flow control correctly. True
functional broadcast with multi-ECU gather (send single-frame on 0x7DF, then run
one physical ISO-TP session per responder) is the next step — see protocol/obd2
Ticket 5. The ``functional`` flag is accepted for interface compatibility.
"""
from __future__ import annotations

import select

from .base import EcuResponse, Transport, TransportError

# ISO 15765-4 standard 11-bit addresses.
OBD_FUNCTIONAL_ID = 0x7DF
OBD_ECU_REQUEST_BASE = 0x7E0   # tester -> ECU n physical
OBD_ECU_RESPONSE_BASE = 0x7E8  # ECU n  -> tester


class SocketCanTransport(Transport):
    """ISO-TP request/response over a (v)can interface.

    Args:
        channel:  SocketCAN interface name, e.g. ``"can0"`` or ``"vcan0"``.
        ecu:      target ECU index (0 = primary powertrain -> 0x7E0/0x7E8).
        extended: use 29-bit addressing (0x18DA.. / 0x18DB33F1) instead of 11-bit.
    """

    def __init__(self, channel: str = "can0", *, ecu: int = 0, extended: bool = False):
        self.channel = channel
        self.ecu = ecu
        self.extended = extended
        self._sock = None  # isotp.socket, created on open()

    # -- lifecycle -----------------------------------------------------------
    def open(self) -> None:
        try:
            import isotp  # can-isotp; imported lazily so the module loads off-Linux
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise TransportError(
                "can-isotp not available: `pip install can-isotp` and load the "
                "kernel module with `sudo modprobe can_isotp` (Linux only)."
            ) from exc

        tx = OBD_ECU_REQUEST_BASE + self.ecu
        rx = OBD_ECU_RESPONSE_BASE + self.ecu
        mode = (
            isotp.AddressingMode.Normal_29bits
            if self.extended
            else isotp.AddressingMode.Normal_11bits
        )
        address = isotp.Address(mode, txid=tx, rxid=rx)
        try:
            self._sock = isotp.socket()
            # Flow control we advertise to the ECU when *we* receive multi-frame.
            self._sock.set_fc_opts(stmin=5, bs=8)
            self._sock.bind(self.channel, address)
        except OSError as exc:  # pragma: no cover - environment dependent
            self._sock = None
            raise TransportError(
                f"cannot open ISO-TP on {self.channel!r}: {exc}"
            ) from exc

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    # -- request/response ----------------------------------------------------
    def request(
        self,
        payload: bytes,
        *,
        functional: bool = True,
        timeout: float = 1.0,
    ) -> list[EcuResponse]:
        if self._sock is None:
            raise TransportError("transport not open — call open() first")

        rx = OBD_ECU_RESPONSE_BASE + self.ecu
        try:
            self._sock.send(bytes(payload))
        except OSError as exc:  # pragma: no cover - environment dependent
            raise TransportError(f"ISO-TP send failed: {exc}") from exc

        # Wait for the (reassembled) reply without blocking forever.
        ready, _, _ = select.select([self._sock], [], [], timeout)
        if not ready:
            return []  # no answer — not an error
        try:
            data = self._sock.recv()
        except OSError as exc:  # pragma: no cover - environment dependent
            raise TransportError(f"ISO-TP recv failed: {exc}") from exc

        if not data:
            return []
        return [EcuResponse(source=rx, data=bytes(data))]

    def receive(self, *, timeout: float = 1.0) -> list[EcuResponse]:
        # Read a further reassembled reply without sending (UDS 0x78 pending).
        if self._sock is None:
            raise TransportError("transport not open — call open() first")
        rx = OBD_ECU_RESPONSE_BASE + self.ecu
        ready, _, _ = select.select([self._sock], [], [], timeout)
        if not ready:
            return []
        try:
            data = self._sock.recv()
        except OSError as exc:  # pragma: no cover - environment dependent
            raise TransportError(f"ISO-TP recv failed: {exc}") from exc
        if not data:
            return []
        return [EcuResponse(source=rx, data=bytes(data))]
