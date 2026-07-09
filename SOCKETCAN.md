# SocketCAN diagnostic stack

The new, hardware-agnostic core of Libre Diagnostic. The vehicle is reached
through a **transport interface**; SocketCAN + kernel ISO-TP is the first-class
backend, ELM327 stays as a secondary one, and everything is testable on a
virtual bus with no car and no adapter.

```
gui/                Tkinter UI (unchanged)
protocol/           OBD-II (J1979) + UDS (ISO 14229) — speaks "read_vin", not CAN frames
  ├─ obd2.py        Mode 01 / 03 / 09 helpers
  └─ dtc.py         DTC <-> 2-byte codec (SAE J2012)
transport/          one interface, many backends
  ├─ base.py        Transport ABC + EcuResponse
  ├─ socketcan.py   SocketCAN + kernel ISO-TP  (Linux, first-class)
  ├─ fake.py        in-memory backend for tests / GUI dev (any OS)
  └─ elm327.py      ELM327 over serial          (secondary — TODO)
simulator/
  └─ ecu_sim.py     virtual OBD-II ECU on vcan
```

## Why SocketCAN

- **The kernel does ISO-TP.** Multi-frame replies (VIN, long DTC lists, UDS DIDs)
  are reassembled by the `can_isotp` module — no hand-rolled segmentation.
- **Testable with zero hardware.** `vcan0` + the ECU simulator = full integration
  tests in CI.
- **Escapes ELM327 clone roulette** and unlocks 29-bit addressing and CAN FD.

Trade-off: SocketCAN is **Linux only**. Non-Linux users fall back to the ELM327
backend.

## Quick start (Linux)

```bash
pip install -r requirements-socketcan.txt
sudo modprobe can_isotp                 # once per boot
./scripts/vcan_up.sh                     # create + up vcan0
python -m simulator.ecu_sim &            # virtual ECU on vcan0
pytest                                   # unit + vcan integration tests
```

Point at real hardware by swapping the channel, e.g.:

```bash
sudo ip link set can0 up type can bitrate 500000
```
```python
from transport.socketcan import SocketCanTransport
from protocol.obd2 import read_vin, read_dtcs

with SocketCanTransport("can0", ecu=0) as t:
    print(read_vin(t))
    print(read_dtcs(t))
```

## Testing model

| Test file                   | Needs         | Runs on            |
|-----------------------------|---------------|--------------------|
| `tests/test_protocol_unit.py` | nothing     | any OS (incl. Windows) |
| `tests/test_socketcan_vin.py` | Linux + vcan | Linux CI / dev box |

The unit tests drive the protocol layer through `FakeTransport`; the integration
test proves the real SocketCAN + ISO-TP path (including multi-frame VIN) against
the simulator, and skips itself when `vcan0` isn't available.

## Status / roadmap

Done: transport interface, SocketCAN ISO-TP backend (physical addressing to one
ECU), VIN + DTC + a few live PIDs, virtual ECU, both test tiers.

Next: functional broadcast + multi-ECU gather, full Mode 01 PID/formula table,
ELM327 backend behind the same interface, GUI de-threading, UDS via `udsoncan`.
See the ticket list in the project notes.
