"""A virtual OBD-II ECU on a (v)can bus — hardware-free development and CI.

Answers a small set of J1979 services over ISO-TP so the SocketCAN transport and
the protocol layer can be exercised without a car. Linux + ``can-isotp`` only.

Bring up a virtual bus, then run the simulator:

    sudo modprobe vcan can_isotp
    sudo ip link add dev vcan0 type vcan
    sudo ip link set up vcan0
    python -m simulator.ecu_sim            # serves on vcan0 until Ctrl-C

In another terminal you can watch the traffic with ``candump vcan0`` or point
the real tool at ``vcan0``. The integration tests spin this up automatically.
"""
from __future__ import annotations

import threading

from protocol.dtc import encode_dtc

# ISO 15765-4 physical addressing for ECU #0 (primary powertrain).
TESTER_TO_ECU = 0x7E0
ECU_TO_TESTER = 0x7E8

DEFAULT_VIN = "1HGCM82633A004352"  # a valid 17-char VIN (Honda Accord)

# A small Mode 01 table. Values chosen to decode to round numbers:
#   RPM      = ((0x1A*256)+0xF8)/4 = 1726 rpm
#   Speed    = 0x50                = 80 km/h
#   Coolant  = 0x5A - 40           = 50 degC
#   Load     = 0x7F * 100/255      ~= 49.8 %
#   Throttle = 0x33 * 100/255      ~= 20 %
_MODE01 = {
    0x04: bytes([0x7F]),
    0x05: bytes([0x5A]),
    0x0C: bytes([0x1A, 0xF8]),
    0x0D: bytes([0x50]),
    0x0F: bytes([0x46]),        # intake temp = 0x46 - 40 = 30 degC
    0x11: bytes([0x33]),
}


def _supported_bitmap(base: int, supported: set[int]) -> bytes:
    """4-byte Mode 01 support bitmask for the range (base+1 .. base+0x20)."""
    bits = 0
    for i in range(32):
        if (base + i + 1) in supported:
            bits |= 1 << (31 - i)
    return bits.to_bytes(4, "big")


class SimulatedEcu:
    """Minimal OBD-II responder served on a background thread.

    Args:
        channel: SocketCAN interface to serve on (default ``"vcan0"``).
        vin:     VIN returned for Mode 09 PID 02.
        dtcs:    stored DTCs returned for Mode 03.
    """

    def __init__(
        self,
        channel: str = "vcan0",
        *,
        vin: str = DEFAULT_VIN,
        dtcs: list[str] | None = None,
    ):
        self.channel = channel
        self.vin = vin
        self.dtcs = dtcs if dtcs is not None else ["P0301", "P0420"]
        self._sock = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> "SimulatedEcu":
        import isotp

        address = isotp.Address(
            isotp.AddressingMode.Normal_11bits,
            txid=ECU_TO_TESTER,
            rxid=TESTER_TO_ECU,
        )
        self._sock = isotp.socket()
        self._sock.bind(self.channel, address)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def __enter__(self) -> "SimulatedEcu":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- serving -------------------------------------------------------------
    def _serve(self) -> None:
        import select

        while not self._stop.is_set():
            ready, _, _ = select.select([self._sock], [], [], 0.2)
            if not ready:
                continue
            try:
                req = self._sock.recv()
            except OSError:
                break
            if not req:
                continue
            resp = self._handle(bytes(req))
            if resp is not None:
                try:
                    self._sock.send(resp)
                except OSError:
                    break

    def _handle(self, req: bytes) -> bytes | None:
        mode = req[0]

        if mode == 0x09 and len(req) >= 2 and req[1] == 0x02:
            # Mode 09 PID 02 (VIN): 49 02 <num_msgs=1> <17 ascii bytes> (multi-frame)
            return bytes([0x49, 0x02, 0x01]) + self.vin.encode("ascii")

        if mode == 0x03:
            # Mode 03 (stored DTCs): 43 <count> <2 bytes per DTC>
            body = bytearray([0x43, len(self.dtcs)])
            for code in self.dtcs:
                body += encode_dtc(code)
            return bytes(body)

        if mode == 0x01 and len(req) >= 2:
            pid = req[1]
            if pid in (0x00, 0x20, 0x40):
                # Supported-PID bitmask; advertise the next range only if we have
                # PIDs beyond it. Here all our PIDs live in the 0x01..0x20 range.
                return bytes([0x41, pid]) + _supported_bitmap(pid, set(_MODE01))
            value = _MODE01.get(pid)
            if value is not None:
                return bytes([0x41, pid]) + value

        # Anything else: negative response 7F <mode> 12 (subFunctionNotSupported).
        return bytes([0x7F, mode, 0x12])


def main() -> None:  # pragma: no cover - manual/interactive entry point
    import time

    print(f"[sim] serving OBD-II ECU on vcan0 (VIN={DEFAULT_VIN}) — Ctrl-C to stop")
    ecu = SimulatedEcu("vcan0").start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        ecu.stop()
        print("\n[sim] stopped")


if __name__ == "__main__":  # pragma: no cover
    main()
