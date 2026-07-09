"""Tests for the DTC library (assets/dtc_library.json) lookup layer."""
from __future__ import annotations

from protocol.dtc_library import category, describe, lookup, manufacturers


def test_generic_lookup():
    entry = lookup("P0001")
    assert entry is not None
    assert entry["source"] == "generic"
    assert entry["definition"].startswith("Fuel Volume Regulator")
    assert entry["category"] == "Fuel System"


def test_lowercase_and_whitespace_normalised():
    assert lookup("  p0001 ") == lookup("P0001")


def test_oem_lookup_via_alias():
    # "ford" alias resolves to the "Ford" OEM sheet; P1000 is Ford-specific.
    entry = lookup("P1000", make="ford")
    assert entry is not None
    assert entry["source"] == "Ford"
    assert "Monitor Testing Not Complete" in entry["definition"]


def test_oem_code_without_make_is_unknown():
    # P1xxx is manufacturer-specific; without a make it is not in the generic table.
    assert lookup("P1000") is None


def test_generic_still_resolves_when_make_given():
    entry = lookup("P0001", make="Toyota")
    assert entry is not None
    assert entry["source"] == "generic"


def test_unknown_code():
    assert lookup("P3FFF") is None
    assert describe("P3FFF") == "Manufacturer-specific or undocumented"
    assert category("P3FFF") is None


def test_manufacturers_listed():
    names = manufacturers()
    assert "Ford" in names and "BMW" in names and "VW Audi" in names
    assert len(names) == 10
