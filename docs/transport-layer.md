# Transport Layer

`transport/base.py` is the seam between _what_ you ask the vehicle and _how_ the
bytes travel. Everything above it (OBD-II, UDS, KWP2000) depends only on the
`Transport` interface, so the same protocol code runs over any backend.

## The interface

```python
from transport.base import Transport, EcuResponse, TransportError

class Transport(ABC):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def request(self, payload: bytes, *, functional: bool = True,
                timeout: float = 1.0) -> list[EcuResponse]: ...
    def receive(self, *, timeout: float = 1.0) -> list[EcuResponse]: ...
    # context manager: `with SomeTransport(...) as t:`
```

- **`payload`** is the raw service payload — service id + data, e.g. `b"\x09\x02"`
  (Mode 09 PID 02, VIN) or `b"\x22\xF1\x90"` (UDS RDBI 0xF190). No framing.
- **`functional`** — broadcast to all ECUs and gather every reply (`True`), or
  address a single ECU (`False`). UDS uses physical (`False`); OBD-II discovery
  uses functional.
- **`receive()`** — read a _further_ reply without sending. Needed for UDS
  response-pending (NRC 0x78): the ECU sends `7F <sid> 78`, then the real answer.

### `EcuResponse`

```python
@dataclass(frozen=True)
class EcuResponse:
    source: int     # responder address, e.g. 0x7E8..0x7EF for 11-bit OBD-II
    data: bytes     # reassembled service response, e.g. b"\x49\x02\x01..." (VIN)

    @property
    def service(self) -> int:      # data[0], the response SID (request SID + 0x40)
    @property
    def is_negative(self) -> bool: # True for 7F <sid> <nrc>
```

### The empty-list contract

`request()` returns a **possibly-empty list**. An empty list means _the vehicle
did not answer_ — this is normal (unsupported PID, wrong ECU) and **must not
raise**. Only real I/O failures raise `TransportError`.

## Backends

### `SocketCanTransport` — first-class (Linux)

```python
from transport.socketcan import SocketCanTransport

t = SocketCanTransport("can0")                 # or "vcan0" for the simulator
t = SocketCanTransport("can0", ecu=1)          # target ECU 1 -> 0x7E1/0x7E9
t = SocketCanTransport("can0", extended=True)  # 29-bit addressing
```

Requires the `can_isotp` kernel module (`sudo modprobe can_isotp`) and the
`can-isotp` Python package. **The kernel does ISO-TP reassembly**, so a multi-frame
VIN/DTC/DID reply comes back as one payload. `isotp` is imported lazily inside
`open()`, so the module still imports on non-Linux machines (it just can't open).

Addressing (ISO 15765-4):

| Direction | 11-bit | 29-bit |
|---|---|---|
| tester → ECU _n_ (physical) | `0x7E0 + n` | `0x18DA(ECU)(F1)` |
| ECU _n_ → tester | `0x7E8 + n` | `0x18DAF1(ECU)` |
| tester → all (functional) | `0x7DF` | `0x18DB33F1` |

> **Current limitation:** the backend opens a _physical_ ISO-TP channel to one ECU
> (correct multi-frame flow control). True functional broadcast with multi-ECU
> gather is the next step; the `functional` flag is accepted for compatibility.

### `Elm327Transport` — secondary (serial / Bluetooth)

```python
from transport.elm327 import Elm327Transport

t = Elm327Transport("/dev/rfcomm0")            # or "COM5" on Windows
t = Elm327Transport("/dev/rfcomm0", baudrate=38400)
```

Sends the service payload as ASCII hex; the adapter builds the CAN frame and
drives ISO-TP itself. Init sequence fixes the classic bugs:

- `ATSP0` (auto protocol) — **not** the old hardcoded `ATSP3` (ISO 9141-2), which
  can't talk to any CAN vehicle (essentially everything post-2008).
- `ATH1` (headers on) — so multi-ECU replies can be demuxed and ISO-TP frames
  reassembled, instead of scraping a fixed `41`/`43` prefix from one line.

The parser (`_parse_elm_response` / `_reassemble_isotp`) groups frames by source
id and reassembles Single/First/Consecutive frames. The serial object is injectable
via `serial_factory=` so the parser is unit-tested with canned output — no hardware.

### `FakeTransport` — tests / offline GUI

```python
from transport.fake import FakeTransport

# dict form: request bytes -> response
bus = FakeTransport({
    b"\x09\x02": b"\x49\x02\x01" + b"1HGCM82633A004352",   # VIN reply
    b"\x01\x0C": b"\x41\x0C\x1A\xF8",                        # RPM = 1726
})

# multi-value list models UDS 0x78: first from request(), rest from receive()
bus = FakeTransport({ b"\x22\xF1\x90": [b"\x7F\x22\x78", b"\x62\xF1\x90..."] })

# callable form for dynamic logic
bus = FakeTransport(lambda payload: [EcuResponse(0x7E8, b"\x41\x00...")])
```

Records every sent payload in `bus.sent` so tests can assert exact request bytes.
Runs on any platform — no CAN, no serial, no kernel modules.

## Choosing a backend at runtime

Don't construct backends in the GUI; go through `DiagnosticSession`:

```python
from obd.session import DiagnosticSession

s = DiagnosticSession.socketcan("can0")      # real vehicle / vcan
s = DiagnosticSession.elm327("/dev/rfcomm0") # dongle
s = DiagnosticSession.simulated({...})       # offline demo
with s:
    print(s.read_vin())
```

## Writing a new backend

1. Subclass `Transport`; implement `open`/`close`/`request` (and `receive` if the
   medium can deliver a follow-up without a new send).
2. Return `[EcuResponse(source, reassembled_bytes), ...]`; **never** raise on "no
   answer" — return `[]`.
3. Do all framing/segmentation inside the backend; hand the protocol layer clean
   service payloads.
4. Make any hardware dependency lazily imported so the module loads everywhere,
   and accept an injection point (like `serial_factory`) for hardware-free tests.
