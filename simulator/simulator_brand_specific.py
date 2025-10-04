# simulator/dtc_simulator.py
from __future__ import annotations
import json, random
from pathlib import Path
from typing import Dict, List, Tuple

# Folder with brand JSONs (e.g., audi.json, bmw.json, volkswagen.json)
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "manufacturer_specific_dtc"

# In-memory session store: which simulated codes are currently “active” per brand
_sim_memory: Dict[str, List[str]] = {}


def _brand_file(brand: str) -> Path:
    """Return the JSON path for a brand (lowercased, hyphen/space tolerant)."""
    fname = brand.strip().lower().replace(" ", "").replace("-", "") + ".json"
    return ASSETS_DIR / fname


def available_brands() -> List[str]:
    """List brands we can simulate (derived from JSON filenames)."""
    brands = []
    if ASSETS_DIR.exists():
        for p in sorted(ASSETS_DIR.glob("*.json")):
            name = p.stem
            # nice title-case for display (volkswagen -> Volkswagen)
            brands.append(name.capitalize())
    return brands


def _load_dtc_map(brand: str) -> Dict[str, str]:
    """
    Load the brand's DTC map { "P1234": "Description", ... }.
    Returns {} if brand file missing / invalid.
    """
    path = _brand_file(brand)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # allow either {"codes": {...}} or flat map for flexibility
        if isinstance(data, dict) and "codes" in data and isinstance(data["codes"], dict):
            return {str(k): str(v) for k, v in data["codes"].items()}
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def simulate_read_brand_dtc(brand: str) -> List[Tuple[str, str]]:
    """
    Deterministic per session: if we already generated codes for this brand,
    return them; otherwise pick 0–2 random codes and remember them.
    """
    key = brand.strip().lower()
    dtc_map = _load_dtc_map(key)
    codes = _sim_memory.get(key)

    if codes is None:
        if not dtc_map:
            _sim_memory[key] = []
            return []
        pool = list(dtc_map.keys())
        n = random.choice([0, 1, 2])
        codes = random.sample(pool, k=min(n, len(pool)))
        _sim_memory[key] = codes

    return [(c, dtc_map.get(c, "Unknown code")) for c in codes]


def clear_brand_dtc(brand: str) -> None:
    """Clear (simulate erase) current active codes for brand."""
    key = brand.strip().lower()
    _sim_memory[key] = []


def has_active_codes(brand: str) -> bool:
    """Check if brand currently has simulated active codes."""
    key = brand.strip().lower()
    return bool(_sim_memory.get(key))
