# Libre Automotive Diagnostic — Developer Documentation

Welcome. This folder is the on-ramp for anyone working on the diagnostic core.
If you're new, read this page, then [`architecture.md`](architecture.md), then the
doc for whichever subsystem you're touching.

## What this project is now

Libre Diagnostic started as a Tkinter GUI that talked to an ELM327 Bluetooth
dongle and scraped ASCII hex out of it. We've kept the GUI and the spirit, and
rebuilt the **diagnostic core** underneath it into a proper, layered, testable
protocol stack:

- A **backend-neutral transport layer** — the same protocol code runs over
  **SocketCAN + kernel ISO-TP** (first-class), an **ELM327** dongle (secondary),
  or an **in-memory fake** (tests, offline GUI).
- Full **SAE J1979 OBD-II** — all ten modes (0x01–0x0A).
- Full **ISO 14229 UDS** — every service 0x10–0x87.
- **ISO 14230 KWP2000** and a **Ford CAN Generic Diagnostic Spec (2003)** profile.
- **SecurityAccess (0x27)** with a ported, verified library of ~40 real seed/key
  algorithms and 3,000+ ECU definitions (from jglim/UnlockECU, MIT).
- A **3,251-entry DTC library** (generic + 10 OEM sets) with decode + lookup.
- A **proper VIN decoder** (ISO 3779: check digit, WMI→manufacturer, model year).
- A **virtual-CAN (vcan) ECU simulator** so the whole stack is testable with **no
  hardware**, in CI.

The old non-compiling C prototype has been moved to
[`archive/hardware-c/`](../archive/hardware-c/ARCHIVE_NOTE.md) for reference.

## The 60-second mental model

```
              ┌──────────────────────────────────────────────┐
  GUI  ─────▶ │  DiagnosticSession  (obd/session.py)          │  one seam the UI uses
              └──────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
        ▼                         ▼                              ▼
  protocol/obd2.py         protocol/uds.py               protocol/kwp2000.py
   (J1979, 10 modes)      (ISO 14229, all svcs)          (ISO 14230)   + ford_gds.py
        │                         │  └── security/ (0x27 seed-key)      + vin.py
        └─────────────┬───────────┴──────────────┬──────────────────────┘
                      ▼                           ▼
              protocol/dtc*.py             protocol/nrc.py
              (DTC codec + library)        (0x7F negative-response codes)
                      │
        ┌─────────────┴──────────────────────────────────────────┐
        ▼  Transport (transport/base.py) — one interface, 3 backends
   SocketCanTransport      Elm327Transport            FakeTransport
   (Linux, kernel ISO-TP)  (serial/Bluetooth)         (tests / offline)
```

Everything above the transport speaks in **service payloads** (`b"\x09\x02"` =
Mode 09 VIN). Everything below hides framing (ISO-TP segmentation, ELM ASCII).

## Documentation map

| Doc | What it covers |
|---|---|
| [architecture.md](architecture.md) | The layers, the "why SocketCAN", design rules |
| [transport-layer.md](transport-layer.md) | `Transport` ABC, SocketCAN / ELM327 / Fake backends, addressing |
| [obd2-j1979.md](obd2-j1979.md) | All 10 OBD-II modes, PIDs, live data, DTCs, VIN |
| [uds-iso14229.md](uds-iso14229.md) | Full UDS service set, sessions, DIDs, routines, security |
| [kwp2000.md](kwp2000.md) | ISO 14230 KWP2000 client |
| [ford-gds.md](ford-gds.md) | Ford CAN Generic Diagnostic Spec (2003) profile |
| [security-access-0x27.md](security-access-0x27.md) | Seed/key unlocking, the UnlockECU port, `db.json` |
| [dtc-library.md](dtc-library.md) | DTC codec + the ingested definition library |
| [negative-response-codes.md](negative-response-codes.md) | The 0x7F NRC table (ISO 14229 + legacy KWP) |
| [vin-decoder.md](vin-decoder.md) | VIN decoding (WMI, check digit, model year) |
| [vcan-and-testing.md](vcan-and-testing.md) | Virtual CAN bus, the ECU simulator, running tests |
| [contributing.md](contributing.md) | Dev setup, conventions, how to add a PID / algorithm / subsystem |

## Quick start (no hardware needed)

```python
from transport.fake import FakeTransport
from protocol import obd2

# Canned ECU: Mode 09 PID 02 (VIN) reply, reassembled for us.
bus = FakeTransport({
    b"\x09\x02": b"\x49\x02\x01" + b"1HGCM82633A004352",
})
with bus:
    print(obd2.read_vin(bus))   # -> 1HGCM82633A004352
```

On Linux with a virtual CAN bus (see [vcan-and-testing.md](vcan-and-testing.md)):

```bash
sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0
python -m pytest        # the suite runs the stack against a simulated ECU on vcan0
```

## Standards this stack implements

SAE J1979 (OBD-II) · ISO 15765-2 (ISO-TP, via the kernel) · ISO 15765-4 (OBD-on-CAN
addressing) · ISO 14229-1 (UDS) · ISO 14230-3 (KWP2000) · SAE J2012 / ISO 15031-6
(DTC format) · ISO 3779 (VIN).
