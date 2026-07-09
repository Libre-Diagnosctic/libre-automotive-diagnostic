# VIN Decoder (`protocol/vin.py`)

Turns a 17-character VIN into a fully populated `VinInfo` — manufacturer, region,
country, model year, plant, serial, and a validated check digit. It's
transport-agnostic: feed it whatever `obd2.read_vin()` (or any source) returned.

```python
from protocol.vin import decode_vin

info = decode_vin("1HGCM82633A004352")
info.manufacturer      # "Honda"
info.model_year        # 2003
info.country           # "United States"
info.valid_check_digit # True
str(info)              # "1HGCM82633A004352: 2003 Honda (United States) [check digit ok]"
```

## The `VinInfo` model

```python
@dataclass
class VinInfo:
    vin: str
    wmi, vds, vis: str | None          # the three sections
    manufacturer: str | None
    region, country: str | None
    model_year: int | None
    model_year_source: str | None      # which heuristic rule fired
    plant_code: str | None             # char 11
    serial_number: str | None          # chars 12-17
    check_digit: str | None            # char 9 as read
    valid_check_digit: bool
    errors: list[str]                  # every problem found
    # .is_valid  -> no structural errors
    # .to_dict() -> JSON-friendly dict
```

**`decode_vin` never raises.** Bad length, illegal letters, an uncomputable check
digit — each becomes an entry in `.errors`, and the object still carries whatever
could be derived. This matters when the VIN came off a flaky bus.

## What it decodes

### Sections (ISO 3779)
`WMI` = chars 1–3 (who built it), `VDS` = chars 4–9 (char 9 is the check digit),
`VIS` = chars 10–17 (char 10 = model year, char 11 = plant, 12–17 = serial). The
letters **I, O, Q are forbidden** (ambiguous with 1/0) and flagged if present.

### Check digit (FMVSS 565 / North American)
`compute_check_digit(vin)` transliterates each character, applies the positional
weights `(8,7,6,5,4,3,2,10,0,9,8,7,6,5,4,3,2)`, sums mod 11, and maps 10 → `X`.
`valid_check_digit` is whether char 9 matches.

> Only North American VINs are *required* to carry a valid check digit; a mismatch
> on an EU/JP VIN is noted in `.errors` but doesn't mean the VIN is wrong.

### Model year (the 30-year ambiguity)
Char 10 cycles through a 30-code alphabet, so `A` could be 1980 *or* 2010. The
decoder disambiguates with the industry-standard heuristic: **char 7 is a digit →
1980–2009 cycle; char 7 is a letter → 2010–2039 cycle.** The rule that fired is
recorded in `model_year_source`, so the guess is always auditable.

### Manufacturer + geography
A ~250-entry `WMI → manufacturer` table (Ford, GM marques, Toyota/Lexus,
Honda/Acura, VW/Audi, BMW/MINI, Mercedes, Hyundai/Kia/Genesis, Tesla, the European
exotica, NA heavy trucks, and Chinese/Indian/South-American/Russian makers).
Unknown WMIs fall back to region/country (ISO 3780 first/second-character ranges)
with `manufacturer=None` and a note.

## Pairing with the live VIN read

```python
from protocol import obd2
from protocol.vin import decode_vin

raw = obd2.read_vin(transport)         # Mode 09 PID 02, e.g. "1FTFW1ET5DFC10312"
info = decode_vin(raw)
print(info.manufacturer, info.model_year, info.country)   # Ford 2013 United States
```

## Extending the tables

- **New WMI:** add a row to `_WMI_MANUFACTURER` (`"XYZ": "Make"`).
- **New/again country range:** add to `_COUNTRY_2CHAR` (checked before the coarse
  `_REGION_1CHAR` fallback).
- The year cycle and check-digit tables are standardised — don't touch them without
  a spec reference.
