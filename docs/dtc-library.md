# DTC Library (`protocol/dtc.py` + `protocol/dtc_library.py`)

Two pieces: a **codec** that turns bytes on the wire into a display code, and a
**library** that turns a display code into a human definition.

## The codec — `protocol/dtc.py`

A DTC is two bytes (SAE J2012 / ISO 15031-6):

```
bit 15-14 : category    0=P powertrain  1=C chassis  2=B body  3=U network
bit 13-12 : first digit 0..3
bit 11-8  : second digit (hex)
bit 7-0   : third + fourth digits (hex)
```

```python
from protocol.dtc import decode_dtc, encode_dtc

decode_dtc(0x01, 0x34)   # "P0134"
encode_dtc("P0134")      # b"\x01\x34"   (inverse; used by the simulator + round-trip tests)
```

This binary form is what SocketCAN sees directly; the ELM327 backend produces the
same codes from its ASCII output, so downstream code is identical.

## The library — `protocol/dtc_library.py`

Backed by `assets/dtc_library.json`, generated from `Automotive_DTC_Library.xlsx`.
Current contents: **1,579 generic** codes (P/B/C/U) + **1,672 OEM** codes across
**10 manufacturer groups**.

```python
from protocol.dtc_library import describe, lookup, category, manufacturers

describe("P0301")                    # "Cylinder 1 Misfire Detected"
lookup("P1000", make="Ford")         # {"code","definition","category","source"} or None
category("P0420")                    # e.g. "Catalyst System"
manufacturers()                      # ["BMW","Ford","GM Chevrolet", ...]
```

**Resolution order:** with a `make`, an OEM-specific definition wins; otherwise (or
on an OEM miss) the generic table is used. Unknown codes return `None` from
`lookup` and a sensible placeholder from `describe`.

### Make aliases

You don't need the exact sheet name. `_MAKE_ALIASES` maps common brand/marque names
to the OEM sheet — e.g. `chevy`, `gmc`, `cadillac`, `buick` → `GM Chevrolet`;
`lincoln` → `Ford`; `dodge`, `jeep`, `ram`, `chrysler`, `fiat` → `Stellantis`;
`lexus` → `Toyota Lexus`; `audi`, `vw` → `VW Audi`; `mini` → `BMW`; and so on.

## Regenerating the library

The JSON is generated, not hand-edited. If the spreadsheet changes:

```bash
python scripts/import_dtc_library.py
```

The importer:
- skips the `Cover` sheet and any banner rows,
- finds each sheet's `DTC Code | Definition | Category` header dynamically,
- routes the 4 generic sheets into `"generic"` and the OEM sheets into
  `"oem"[<sheet name>]`,
- writes `assets/dtc_library.json` as
  `{"meta": {...}, "generic": {...}, "oem": {<make>: {...}}}`.

Output shape consumed by `dtc_library.py`:

```json
{
  "generic": { "P0301": {"definition": "Cylinder 1 Misfire Detected", "category": "Ignition"} },
  "oem":     { "Ford": { "P1000": {"definition": "...", "category": "..."} } }
}
```

## How the pieces connect

```
wire bytes ──decode_dtc──▶ "P0301" ──dtc_library.lookup(make)──▶ {definition, category}
```

`obd2.describe_dtcs(codes, make)` chains them, and `J1979.stored_dtcs(detailed=True)`
returns the enriched records ready for the GUI.
