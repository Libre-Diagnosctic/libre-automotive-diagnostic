# Ford CAN Generic Diagnostic Specification (`protocol/ford_gds.py`)

Ford's CAN GDS (~2003) is **not a new protocol** — it's ISO 14230 (KWP2000) carried
over CAN/ISO-TP, with Ford-specific addressing and a Ford catalog of identifiers.
So this module reuses `KWP2000Client` unchanged and only adds the module address map
and the Ford identifier catalog.

```python
from transport.socketcan import SocketCanTransport
from protocol.ford_gds import FordGDS, FordModule

with SocketCanTransport("can0", ecu=0) as t:
    gds = FordGDS(t, module=FordModule.PCM)
    gds.enter_extended_session()
    print(gds.read_vin())                 # via DID 0xF190
    print(gds.read_calibration_level())   # via DID 0xF124
    dtcs = gds.read_dtcs()                # 0x18 ReadDTCsByStatus
```

## Provenance — read this before trusting a value

This is the honest part, and it's baked into the module:

- **Service layer — authoritative.** SIDs, framing, NRC handling are ISO 14230-3,
  delegated entirely to `protocol/kwp2000.py`. Nothing is reimplemented.
- **Powertrain addressing — authoritative (ISO 15765-4):** `PCM` 0x7E0/0x7E8, `TCM`
  0x7E1/0x7E9, functional broadcast 0x7DF.
- **Everything else — inferred.** The other `FordModule` addresses (ABS, RCM/airbag,
  IPC, BCM, PAM, ACM, HVAC) and most Ford DIDs/LIDs are **community-documented /
  commonly-observed**, not from an authoritative public Ford spec. They vary by
  vehicle line, model year, and network (HS-CAN vs MS-CAN), and are often reached
  through a gateway.

Each `FordModule` member carries an `authoritative` flag; check it:

```python
FordModule.PCM.authoritative   # True  (ISO 15765-4)
FordModule.ABS.is_inferred      # True  (confirm against the specific vehicle)
```

DIDs/LIDs are catalogued with the same honesty — `FORD_DIDS[did]` is `(name,
authoritative)`:

```python
from protocol.ford_gds import FORD_DIDS, FORD_DID_VIN, FORD_DID_CALIBRATION_LEVEL
FORD_DIDS[FORD_DID_VIN]                 # ("VIN", True)           ISO-standard
FORD_DIDS[FORD_DID_CALIBRATION_LEVEL]   # ("Calibration level", False)  inferred
```

## The `FordGDS` facade

| Method | Does |
|---|---|
| `enter_extended_session()` | 0x10 0x92 |
| `enter_default_session()` | 0x10 0x81 |
| `tester_present(response_required=)` | 0x3E keep-alive |
| `read_vin()` | DID 0xF190 → ASCII string |
| `read_calibration_level()` | DID 0xF124 (inferred) → string |
| `read_part_number(did=…)` | strategy/calibration part-number DID (inferred) |
| `read_data_by_identifier(did)` | 0x22 raw record |
| `read_data_by_local_identifier(lid)` | 0x21 raw record |
| `read_dtcs(status, group)` | 0x18 → `[{code,status,flags}]` |
| `clear_dtcs(group)` | 0x14 |
| `security_access_request_seed(level)` / `security_access_send_key(level, key)` | 0x27 |

## SecurityAccess note

Ford's seed→key algorithm is proprietary and vehicle/module specific, so `FordGDS`
deliberately does **not** ship a Ford key function. Request the seed, compute the
key with your own function (or a `protocol.security` provider if one matches the
target ECU), then send it:

```python
seed = gds.security_access_request_seed(0x01)
gds.security_access_send_key(0x01, my_ford_key(seed))
```

## Addressing caveat

`FordModule` exposes `request_id` / `response_id` so a caller can build the transport
with the right addressing. The current `SocketCanTransport` targets a powertrain ECU
by index (0x7E0+n / 0x7E8+n), which covers PCM/TCM directly; reaching the inferred
body/chassis modules on their non-standard IDs is a transport-configuration step to
finish per vehicle. When in doubt, sniff the bus with `candump` first.
