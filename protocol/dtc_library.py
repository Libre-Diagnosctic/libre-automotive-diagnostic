"""DTC definition lookup backed by assets/dtc_library.json.

Resolves a diagnostic trouble code (e.g. ``"P0301"``) to its human definition and
category. Generic SAE/ISO codes are looked up directly; manufacturer-specific
codes (P1xxx, etc.) are resolved against an OEM table when a make is supplied,
falling back to the generic table.

    from protocol.dtc_library import describe, lookup
    describe("P0301")                 -> "Cylinder 1 Misfire Detected"
    lookup("P1000", make="Ford")      -> {"code": "P1000", "definition": ..., ...}
"""
from __future__ import annotations

import json
from pathlib import Path

_ASSET = Path(__file__).resolve().parent.parent / "assets" / "dtc_library.json"

try:
    _DB = json.loads(_ASSET.read_text(encoding="utf-8"))
except FileNotFoundError:  # pragma: no cover - asset ships with the repo
    print(f"Warning: DTC library not found: {_ASSET} (run scripts/import_dtc_library.py)")
    _DB = {"generic": {}, "oem": {}}

_GENERIC: dict[str, dict[str, str]] = _DB.get("generic", {})
_OEM: dict[str, dict[str, dict[str, str]]] = _DB.get("oem", {})

# Map loose make names / brands to the OEM sheet keys in the library.
_MAKE_ALIASES = {
    "chevrolet": "GM Chevrolet", "chevy": "GM Chevrolet", "gm": "GM Chevrolet",
    "gmc": "GM Chevrolet", "cadillac": "GM Chevrolet", "buick": "GM Chevrolet",
    "ford": "Ford", "lincoln": "Ford",
    "stellantis": "Stellantis", "chrysler": "Stellantis", "dodge": "Stellantis",
    "jeep": "Stellantis", "ram": "Stellantis", "fiat": "Stellantis",
    "toyota": "Toyota Lexus", "lexus": "Toyota Lexus",
    "honda": "Honda Acura", "acura": "Honda Acura",
    "nissan": "Nissan Infiniti", "infiniti": "Nissan Infiniti",
    "hyundai": "Hyundai Kia", "kia": "Hyundai Kia", "genesis": "Hyundai Kia",
    "bmw": "BMW", "mini": "BMW",
    "mercedes": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz", "benz": "Mercedes-Benz",
    "vw": "VW Audi", "volkswagen": "VW Audi", "audi": "VW Audi",
}


def manufacturers() -> list[str]:
    """OEM tables available in the library."""
    return sorted(_OEM)


def _resolve_make(make: str | None) -> str | None:
    if not make:
        return None
    key = make.strip()
    if key in _OEM:
        return key
    return _MAKE_ALIASES.get(key.lower())


def lookup(code: str, make: str | None = None) -> dict | None:
    """Return ``{code, definition, category, source}`` or ``None`` if unknown.

    With ``make`` set, an OEM-specific definition wins; otherwise (or on OEM miss)
    the generic table is used.
    """
    code = code.strip().upper()
    sheet = _resolve_make(make)
    if sheet and code in _OEM.get(sheet, {}):
        entry = _OEM[sheet][code]
        return {"code": code, "source": sheet, **entry}
    if code in _GENERIC:
        return {"code": code, "source": "generic", **_GENERIC[code]}
    return None


def describe(code: str, make: str | None = None) -> str:
    """Human definition for a code, or a sensible placeholder if unknown."""
    entry = lookup(code, make)
    return entry["definition"] if entry else "Manufacturer-specific or undocumented"


def category(code: str, make: str | None = None) -> str | None:
    entry = lookup(code, make)
    return entry.get("category") if entry else None
