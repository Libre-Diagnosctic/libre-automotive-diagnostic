# SecurityAccess 0x27 — Seed/Key Unlocking (`protocol/security/`)

UDS/KWP service 0x27 gates the sensitive stuff (writing calibrations, running
routines, flashing). The ECU sends a random **seed**; the tester must return the
correct **key** computed by a manufacturer algorithm. This package is a faithful
Python port of **[jglim/UnlockECU](https://github.com/jglim/UnlockECU)** (MIT,
© 2020 JinGen Lim) — ~40 reverse-engineered seed/key algorithms plus a 3,000+
entry ECU definition database.

> **Attribution & licensing.** All credit for the original reverse-engineering goes
> to jglim. The upstream project states its algorithms and `db.json` are
> reverse-engineered and contain no proprietary blobs. See
> [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) and
> [`../protocol/security/UNLOCKECU_LICENSE.txt`](../protocol/security/UNLOCKECU_LICENSE.txt).

> **Authorized use only.** Seed/key unlocking is for legitimate diagnostics,
> repair, and research on vehicles you own or are authorized to service.

## Two levels of API

### `compute_key` — pure, offline, testable

```python
from protocol.security import compute_key

# seed comes from the ECU (0x27 request-seed). Given the ECU name + level:
key = compute_key("IC204_2049022600", 9, bytes.fromhex("1122334455667788"))
# -> b'\x62\x1a\xc5\x52\xc1\x96\x8e\x5d'
```

No vehicle needed — this is just math over the seed and the ECU's stored
parameters. It's the unit-test surface for the whole port.

### `unlock` — the full handshake over a live client

```python
from protocol.uds import UDSClient
from protocol.security import unlock

uds = UDSClient(transport)
unlock(uds, "IC204_2049022600", 9)   # request seed → compute key → send key → True
```

`unlock` works with any client exposing `security_access_request_seed(level)` and
`security_access_send_key(level, key)` — i.e. both `UDSClient` and `KWP2000Client`.
An all-zero seed means "already unlocked," so no key is sent.

## How it's put together

```
db.json ──▶ definitions.py ──▶ Definition{ecu, level, provider, key_length, parameters}
                                     │  (which algorithm + which constants)
                                     ▼
registry.py ──▶ get_provider("IC204") ──▶ IC204()  (a SecurityProvider subclass)
                                     │
provider.generate_key(seed, key_length, level, parameters) ──▶ key bytes
```

- **`provider.py`** — the ported `SecurityProvider` base + all the bit/byte
  utilities (`bytes_to_int`, `int_to_bytes`, `rotate_left/right`, nibble
  expand/collapse, `param_int/byte/long/bytes`). C# `uint`/`byte` overflow is
  reproduced with explicit `& 0xFFFFFFFF` / `& 0xFF` masking, and signed Int32/
  Int64 parameters are sign-extended to match C# semantics.
- **`definitions.py`** — loads `assets/unlockecu_db.json` into `Definition`
  objects; `find_definition(ecu_name, level)` mirrors UnlockECU's matcher (level
  must match; name equals `EcuName` or appears in `Aliases`).
- **`registry.py`** — auto-discovers every algorithm: it imports each module in
  `algorithms/` and collects `SecurityProvider` subclasses, keyed by their `NAME`
  (the `Provider` string used in `db.json`). Drop in a new file, it's registered.
- **`algorithms/*.py`** — ~40 ported providers (one file per source `.cs`), e.g.
  `IC204.py`, `VolkswagenSA2.py`, `DaimlerStandardSecurityAlgo.py`, `XorAlgo.py`.
- **`unlock.py`** — `compute_key` (pure) and `unlock` (handshake).

## The definition database (`assets/unlockecu_db.json`)

3,038 definitions. Each entry:

```json
{
  "EcuName": "IC204_2049022600", "Aliases": [], "AccessLevel": 9,
  "SeedLength": 8, "KeyLength": 8,
  "Provider": "IC204",
  "Parameters": [ {"Key": "...", "Value": "....", "DataType": "ByteArray"} ]
}
```

Discover what's available:

```python
from protocol.security import ecu_names, provider_names, find_definition

ecu_names()          # every ECU in the DB
provider_names()     # every registered algorithm
d = find_definition("IC204_2049022600", 9)
d.provider, d.key_length, d.seed_length
```

## Verification — IC204 reference vectors

`IC204` is our ground truth: the upstream test suite ships 15 known
(seed → key) pairs, which our port reproduces exactly. If you touch `provider.py`
or an algorithm, run the security tests — a broken utility will fail these first.

```python
compute_key("IC204_2049022600", 9, bytes.fromhex("0000000000000000")).hex().upper()
# == "7FE64EA513E37FD5"
```

Most other algorithms have **no public reference vectors**, so they are faithful
1:1 translations validated structurally (they import and run on a correct-length
seed). Treat non-IC204 outputs as "matches the reference C# implementation," not
"independently proven against a physical ECU."

## Adding / fixing an algorithm

1. Read the C# in `0x27/0x27-main/UnlockECU/UnlockECU/Security/<Name>.cs`.
2. Create `protocol/security/algorithms/<Name>.py`:

```python
from __future__ import annotations
from typing import List, Optional
from ..provider import SecurityProvider, Parameter, param_bytes, bytes_to_int, int_to_bytes, BIG

class XorAlgo(SecurityProvider):
    NAME = "XorAlgo"                      # EXACT string from C# GetProviderName()
    def generate_key(self, seed, key_length, access_level, parameters) -> Optional[bytes]:
        xor_key = param_bytes(parameters, "K")
        if not (len(seed) == key_length == len(xor_key)):
            return None                  # C# `return false` → Python `return None`
        return bytes(s ^ k for s, k in zip(seed, xor_key))
```

3. **Fidelity rules:** mask every 32-bit intermediate with `& 0xFFFFFFFF`, mask
   bytes with `& 0xFF`, preserve endianness, don't "optimize" the math. `NAME` is
   what the registry keys on — set it to the `GetProviderName()` string, not
   necessarily the class name.
4. The registry picks it up automatically. Add a test if you have vectors.
