"""Convert Automotive_DTC_Library.xlsx into assets/dtc_library.json.

The workbook has one 'Cover' sheet, four generic sheets (P/B/C/U) and ten
OEM-specific sheets. Every data sheet has a ``DTC Code | Definition | Category``
header (col B/C/D); we locate that header row dynamically and read below it.

Output shape:
    {
      "meta":    {"source": ..., "counts": {...}},
      "generic": {"P0001": {"definition": ..., "category": ...}, ...},
      "oem":     {"Ford": {"P1000": {"definition": ..., "category": ...}}, ...}
    }

Run:  python scripts/import_dtc_library.py
"""
from __future__ import annotations

import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "Automotive_DTC_Library.xlsx"
OUT = ROOT / "assets" / "dtc_library.json"

GENERIC_SHEETS = {
    "Generic Powertrain (P0xxx)",
    "Generic Body (B0xxx)",
    "Generic Chassis (C0xxx)",
    "Generic Network (U0xxx)",
}


def _find_header(rows: list[tuple]) -> int | None:
    """Index of the row whose second cell is 'DTC Code'."""
    for i, row in enumerate(rows):
        if len(row) > 1 and isinstance(row[1], str) and row[1].strip().lower() == "dtc code":
            return i
    return None


def _read_sheet(rows: list[tuple]) -> dict[str, dict[str, str]]:
    header = _find_header(rows)
    if header is None:
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in rows[header + 1 :]:
        code = row[1] if len(row) > 1 else None
        if not code or not isinstance(code, str):
            continue
        code = code.strip().upper()
        if not code:
            continue
        definition = (row[2] if len(row) > 2 and row[2] else "").strip()
        category = (row[3] if len(row) > 3 and row[3] else "").strip()
        out.setdefault(code, {"definition": definition, "category": category})
    return out


def main() -> None:
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    generic: dict[str, dict[str, str]] = {}
    oem: dict[str, dict[str, dict[str, str]]] = {}

    for ws in wb.worksheets:
        if ws.title == "Cover":
            continue
        rows = list(ws.iter_rows(values_only=True))
        codes = _read_sheet(rows)
        if not codes:
            print(f"  ! no codes parsed from {ws.title!r}")
            continue
        if ws.title in GENERIC_SHEETS:
            generic.update(codes)
        else:
            oem[ws.title] = codes
        print(f"  {ws.title:<30} {len(codes):>5} codes")

    payload = {
        "meta": {
            "source": XLSX.name,
            "counts": {
                "generic": len(generic),
                "oem_manufacturers": len(oem),
                "oem_codes": sum(len(v) for v in oem.values()),
            },
        },
        "generic": dict(sorted(generic.items())),
        "oem": {k: dict(sorted(v.items())) for k, v in sorted(oem.items())},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"\nWrote {OUT.relative_to(ROOT)}: "
        f"{len(generic)} generic + {payload['meta']['counts']['oem_codes']} OEM "
        f"across {len(oem)} manufacturers"
    )


if __name__ == "__main__":
    main()
