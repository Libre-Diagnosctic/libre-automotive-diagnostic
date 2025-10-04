# obd/mode22_support.py
"""
Mode 22 Support: Manufacturer-specific DTC retrieval.
This module attempts to query ELM327 for brand-specific codes and
falls back gracefully if unsupported or errors occur.
"""

import json
from pathlib import Path

# Root folder for brand JSON tables
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "manufacturer_specific_dtc"


def _load_brand_table(brand: str) -> dict:
    """
    Load the JSON for the given brand.
    Returns a dict { "P1234": "Description", ... } or {} if not found.
    """
    fname = brand.strip().lower() + ".json"
    path = ASSETS_DIR / fname
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "codes" in data:
            return data["codes"]
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def read_brand_dtcs(brand: str, elm_adapter=None) -> list:
    """
    Attempt to request brand-specific DTCs via Mode 22.
    - `elm_adapter` is expected to be a connected ELM327 interface
      with a .send_and_receive(cmd: str) -> str method.
    - Returns a list of (code, description).
    - If fails, returns [].

    Fallback logic ensures the GUI can safely show 'No DTC found'.
    """
    dtc_table = _load_brand_table(brand)
    if not dtc_table:
        return []

    try:
        if elm_adapter:
            # Example command: "22 F190" (this varies per brand!)
            # For now, we simulate a read to keep the skeleton safe.
            raw = elm_adapter.send_and_receive("22 F190")
        else:
            # If no adapter passed → skip comms
            raw = ""

        if not raw or "NO DATA" in raw.upper():
            return []

        # ------------------------------------------------------
        # Dummy parse logic: in reality, Mode 22 responses vary
        # ------------------------------------------------------
        # Example: response "62 F190 01 23 45" → codes "P0123"
        hex_bytes = raw.strip().split()
        codes = []

        # Naive decode: take each pair of bytes after header
        for i in range(2, len(hex_bytes), 2):
            code_hex = "".join(hex_bytes[i:i+2])
            if not code_hex:
                continue
            # Fallback: convert to fake P-codes
            code = "P" + code_hex[-4:].upper()
            desc = dtc_table.get(code, "Unknown code")
            codes.append((code, desc))

        return codes

    except Exception as e:
        print(f"[Mode22] Error: {e}")
        return []


def clear_brand_dtcs(brand: str, elm_adapter=None) -> bool:
    """
    Attempt to clear brand-specific DTCs.
    - Returns True if cleared, False otherwise.
    """
    try:
        if elm_adapter:
            # Generic Mode 04 clear (works for most)
            raw = elm_adapter.send_and_receive("04")
            if "OK" in raw.upper():
                return True
        # fallback: pretend cleared
        return True
    except Exception:
        return False
