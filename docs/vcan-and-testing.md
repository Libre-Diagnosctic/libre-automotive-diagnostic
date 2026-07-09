# Virtual CAN & Testing

The single biggest win of the SocketCAN move: **the whole stack is testable with no
hardware and no vehicle.** Two mechanisms — an in-memory fake for unit tests, and a
virtual CAN bus + ECU simulator for integration tests.

## Level 1 — `FakeTransport` (any platform)

No CAN, no serial, no kernel modules. Perfect for unit tests and offline GUI work.

```python
from transport.fake import FakeTransport
from protocol import obd2

bus = FakeTransport({
    b"\x09\x02": b"\x49\x02\x01" + b"1HGCM82633A004352",   # VIN
    b"\x03":     b"\x43\x02\x01\x34\x04\x20",                # DTCs P0134, P0420
})
with bus:
    assert obd2.read_vin(bus) == "1HGCM82633A004352"
    assert obd2.read_dtcs(bus) == ["P0134", "P0420"]

# assert the exact bytes we put on the wire:
assert bus.sent[0] == b"\x09\x02"
```

Multi-value entries model UDS response-pending (0x78): the first value comes from
`request()`, the rest from `receive()`.

## Level 2 — virtual CAN bus (`vcan0`, Linux)

Bring up a kernel virtual CAN interface — behaves like a real bus, no hardware:

```bash
# scripts/vcan_up.sh does this for you:
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
sudo modprobe can_isotp          # ISO-TP kernel module
```

Watch traffic with `can-utils` while debugging:

```bash
candump vcan0                    # live frames
cansend vcan0 7DF#0209           # hand-send a Mode 09 VIN request
```

## The ECU simulator (`simulator/ecu_sim.py`)

A simulated ECU that binds an ISO-TP socket on `vcan0` and answers OBD-II requests
(Mode 01 live data, Mode 03 DTCs, Mode 09 VIN — multi-frame). It's the counterpart
that makes vcan integration tests meaningful, and it reuses the same `encode_dtc` /
PID table as the real decoders, so simulator and decoder agree by construction.

Run the stack against it:

```bash
python -m simulator.ecu_sim &      # start the simulated ECU on vcan0
python - <<'PY'
from transport.socketcan import SocketCanTransport
from protocol import obd2
with SocketCanTransport("vcan0") as t:
    print(obd2.read_vin(t))        # proves ISO-TP reassembly end-to-end
PY
```

## Running the test suite

```bash
python -m pytest                 # everything
python -m pytest tests/test_uds.py -q
python -m pytest -k security     # just the seed/key tests
```

Tests that need `vcan0` / `can-isotp` skip automatically when the interface or
module isn't present, so the fake-transport tests still run on Windows/macOS and in
plain CI. The Linux CI job (`.github/workflows/ci.yml`) brings up `vcan0` and runs
the full suite including the simulator.

## What to test when you add a feature

| You added… | Test with… |
|---|---|
| A PID decoder | `FakeTransport` with a canned Mode 01 reply |
| A UDS/KWP service | `FakeTransport`; assert `.sent` bytes + parse the reply |
| A seed/key algorithm | `compute_key` with vectors if you have them, else an import/run smoke test |
| A transport backend | Injected fake serial / a vcan round-trip |
| Multi-frame handling | vcan + simulator (real ISO-TP), not just the fake |

**Rule of thumb:** every new protocol capability ships with a hardware-free test.
If it can only be verified against a physical car, it isn't done.
