# Architecture

## The one idea

**Separate _what you ask the vehicle_ from _how the bytes get there._**

Every diagnostic protocol (OBD-II, UDS, KWP2000) is ultimately "send a service
payload, get response payloads back." The messy part — turning that into CAN
frames, segmenting long messages (ISO-TP), handling an ELM327's ASCII quirks — is
_transport_. We put a hard line between the two:

```
protocol layer   speaks service payloads:  b"\x22\xF1\x90"  (UDS ReadDataByIdentifier 0xF190)
     │
     ▼
Transport ABC    request(payload) -> [EcuResponse(source, data), ...]
     │
     ▼
backend          turns that into frames on the wire and reassembles the reply
```

Because the protocol layer only ever sees `Transport`, the exact same J1979 / UDS
code runs unchanged over SocketCAN, an ELM327 dongle, or an in-memory fake.

## Why SocketCAN is the first-class backend

The original tool was married to ELM327 clones, which are the single biggest
source of its bugs (its own README lists "some ELM327 clones return malformed
responses" as a top limitation). SocketCAN fixes this at the root:

1. **The kernel does ISO-TP for you.** The `can_isotp` module (mainlined in Linux
   5.10) handles First Frame / Consecutive Frame / Flow Control / block size /
   STmin. A multi-frame reply — VIN (Mode 09), long DTC lists, UDS DIDs — arrives
   as **one reassembled payload**. The old hand-rolled `custom_isotp.h` in the C
   tree never got this right; now we don't write it at all.
2. **Testable with zero hardware.** A virtual CAN interface (`vcan0`) plus a small
   ECU simulator means the whole stack runs in CI with no dongle and no car.
3. **No clone roulette, and CAN FD is possible.** Raw arbitration IDs, 29-bit
   addressing, real timing.

ELM327 stays as a **secondary** backend behind the same interface, so users with
only a Bluetooth dongle (and non-Linux users) still work.

## The layers, bottom to top

### 1. Transport (`transport/`)
`transport/base.py` defines the seam:

- `Transport` — `open()`, `close()`, `request(payload, *, functional=, timeout=)`,
  `receive(*, timeout=)`, plus context-manager sugar.
- `EcuResponse(source, data)` — one ECU's reassembled reply, with `.service` and
  `.is_negative` helpers.
- `TransportError` — backend open/send/recv failure. **An empty response list is
  not an error** (the vehicle simply didn't answer).

Backends: `SocketCanTransport`, `Elm327Transport`, `FakeTransport`. See
[transport-layer.md](transport-layer.md).

### 2. Protocol (`protocol/`)
Transport-neutral clients that speak vehicle protocols:

- `obd2.py` — SAE J1979, all 10 modes. `J1979` bundle class + module functions.
- `uds.py` — ISO 14229, services 0x10–0x87. `UDSClient` class.
- `kwp2000.py` — ISO 14230 KWP2000. `KWP2000Client`.
- `ford_gds.py` — Ford CAN GDS (2003) profile on top of KWP2000.
- `security/` — SecurityAccess (0x27) seed/key algorithms (ported UnlockECU).
- `nrc.py` — the canonical 0x7F negative-response-code table.
- `dtc.py` + `dtc_library.py` — DTC 2-byte codec and the human-readable library.
- `pids.py` — the Mode 01 PID decode table.
- `vin.py` — ISO 3779 VIN decoder.

### 3. Session (`obd/session.py`)
`DiagnosticSession` is the **single façade the GUI talks to**. It owns a transport
and exposes `read_vin()`, `read_live_data()`, `read_dtcs()`, plus `.j1979()` and
`.uds()` for full access. Factories pick the backend:

```python
DiagnosticSession.socketcan("can0")     # real / vcan
DiagnosticSession.elm327("/dev/rfcomm0")
DiagnosticSession.simulated({...})       # offline
```

### 4. GUI (`gui/`) + threading (`utils/ui_worker.py`)
Tkinter, unchanged in spirit. Long calls run off the UI thread via
`utils/ui_worker.run_async`, which marshals results back with `root.after(...)` so
widgets are only ever touched on the main loop.

## Design rules (please keep these)

1. **Protocol code never imports a concrete backend.** It depends only on
   `transport.base.Transport`. If you're tempted to `import serial` in `protocol/`,
   stop — that belongs in a backend.
2. **An empty response list means "no answer," not an exception.** Only raise
   `TransportError` for real I/O failures.
3. **One source of truth for shared tables.** NRCs live in `protocol/nrc.py`; DTC
   definitions in `assets/dtc_library.json`; PIDs in `protocol/pids.py`. Don't
   copy them into a second place.
4. **Everything is testable without hardware.** New protocol features come with
   `FakeTransport` (or vcan-simulator) tests. See [vcan-and-testing.md](vcan-and-testing.md).
5. **Writes to the vehicle are gated and logged.** Clear-DTC, UDS 0x2E/0x31,
   SecurityAccess — confirm, log, and never ship a fake seed/key as if it were real.

## Directory layout

```
transport/     base.py · socketcan.py · elm327.py · fake.py
protocol/      obd2.py · uds.py · kwp2000.py · ford_gds.py · vin.py
               nrc.py · dtc.py · dtc_library.py · pids.py
               security/   provider.py · registry.py · definitions.py · unlock.py
                           algorithms/*.py   (~40 ported seed/key providers)
obd/           session.py  (façade)  + legacy helpers being folded in
gui/           Tkinter screens
utils/         ui_worker.py (thread marshaling) · log_manager.py
simulator/     ecu_sim.py  (vcan ECU) + data
assets/        dtc_library.json · unlockecu_db.json · pid_profiles.json
scripts/       import_dtc_library.py · vcan_up.sh
tests/         pytest suite (fake-transport + vcan)
archive/       hardware-c/  (old non-compiling C prototype, reference only)
docs/          you are here
```
