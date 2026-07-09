"""Tests for the ISO 3779 / ISO 3780 / NHTSA VIN decoder (``protocol.vin``).

Uses several real (and constructed) VINs with known make / year / origin to
exercise section splitting, the FMVSS 565 check digit, WMI -> manufacturer,
ISO 3780 geography, and the char-7 model-year disambiguation heuristic.
"""
from __future__ import annotations

import pytest

from protocol.vin import (
    VIN_LENGTH,
    VinInfo,
    compute_check_digit,
    decode_vin,
)

# (vin, make, year, region, country, check_digit_valid)
REAL_VINS = [
    ("1HGCM82633A004352", "Honda", 2003, "North America", "United States", True),
    ("11111111111111111", None, 2001, "North America", None, True),
    ("WVWZZZ1JZXW000010", "Volkswagen", 1999, "Europe", "Germany", False),
    ("JH4KA8260MC000000", "Acura", 1991, "Asia", "Japan", False),
    ("5YJSA1E14HF000337", "Tesla", 2017, "North America", "United States", False),
]


# --------------------------------------------------------------------------- #
# Section splitting
# --------------------------------------------------------------------------- #
def test_sections_split_correctly():
    info = decode_vin("1HGCM82633A004352")
    assert info.wmi == "1HG"
    assert info.vds == "CM8263"
    assert info.vis == "3A004352"
    assert info.check_digit == "3"
    assert info.plant_code == "A"
    assert info.serial_number == "004352"
    assert info.is_valid


def test_lowercase_is_normalised():
    info = decode_vin("1hgcm82633a004352")
    assert info.vin == "1HGCM82633A004352"
    assert info.manufacturer == "Honda"
    assert info.valid_check_digit


def test_whitespace_is_stripped():
    info = decode_vin("  1HGCM82633A004352  ")
    assert info.vin == "1HGCM82633A004352"
    assert info.is_valid


# --------------------------------------------------------------------------- #
# Check digit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vin,make,year,region,country,cd_valid", REAL_VINS)
def test_check_digit_matches_expectation(vin, make, year, region, country, cd_valid):
    info = decode_vin(vin)
    assert info.valid_check_digit is cd_valid


def test_honda_check_digit_is_3():
    assert compute_check_digit("1HGCM82633A004352") == "3"


def test_all_ones_check_digit_is_1_by_construction():
    # Every char transliterates to 1; sum of weights (excluding pos 9) = 89;
    # 89 % 11 == 1, so the check digit is '1' and the VIN self-validates.
    assert compute_check_digit("11111111111111111") == "1"
    assert decode_vin("11111111111111111").valid_check_digit


def test_check_digit_x_case():
    # A VIN whose weighted sum mod 11 == 10 must use 'X'. Construct and verify
    # round-trip: replace char 9 with the computed digit and it should validate.
    base = "1M8GDM9AXKP042788"  # known real-world 'X' check-digit VIN (Winnebago)
    expected = compute_check_digit(base)
    assert expected == "X"
    assert decode_vin(base).valid_check_digit


def test_wrong_check_digit_flagged():
    # Flip the Honda check digit to a wrong value.
    info = decode_vin("1HGCM82634A004352")
    assert not info.valid_check_digit
    assert any("check digit" in e for e in info.errors)


# --------------------------------------------------------------------------- #
# Manufacturer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vin,make,year,region,country,cd_valid", REAL_VINS)
def test_manufacturer(vin, make, year, region, country, cd_valid):
    assert decode_vin(vin).manufacturer == make


def test_manufacturer_samples():
    cases = {
        "WBADT43452G034123": "BMW",
        "WDBUF56X48B123456": "Mercedes-Benz",
        "KMHDU46D07U000000": "Hyundai",
        "KNADM4A34C6000000": "Kia",
        "JF1GD70565L000000": "Subaru",
        "ZFF65LHA0F0000000": "Ferrari",
        "WP0AB29925S000000": "Porsche",
        "SALGS2VF9HA000000": "Land Rover",
        "1FTFW1ET5DF000000": "Ford",
        "1G1YY22G965000000": "Chevrolet",
    }
    for vin, make in cases.items():
        assert decode_vin(vin).manufacturer == make, vin


def test_unknown_wmi_falls_back_to_region():
    info = decode_vin("11111111111111111")
    assert info.manufacturer is None
    assert info.region == "North America"
    assert any("not in manufacturer table" in e for e in info.errors)


# --------------------------------------------------------------------------- #
# Region + country (ISO 3780)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vin,make,year,region,country,cd_valid", REAL_VINS)
def test_region_and_country(vin, make, year, region, country, cd_valid):
    info = decode_vin(vin)
    assert info.region == region
    if country is not None:
        assert info.country == country


def test_country_ranges():
    assert decode_vin("JH4KA8260MC000000").country == "Japan"
    assert decode_vin("WVWZZZ1JZXW000010").country == "Germany"
    assert decode_vin("VF1AAAAA000000000").country == "France"
    assert decode_vin("ZFF65LHA0F0000000").country == "Italy"
    assert decode_vin("2HGES16542H000000").country == "Canada"
    assert decode_vin("3VWFE21C04M000000").country == "Mexico"
    assert decode_vin("9BWZZZ377VT000000").country == "Brazil"


# --------------------------------------------------------------------------- #
# Model year + heuristic
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vin,make,year,region,country,cd_valid", REAL_VINS)
def test_model_year(vin, make, year, region, country, cd_valid):
    assert decode_vin(vin).model_year == year


def test_year_heuristic_digit_char7_is_pre_2010():
    # Honda: char 7 == '2' (a digit) -> 1980-2009 cycle. Code '3' -> 2003.
    info = decode_vin("1HGCM82633A004352")
    assert info.vin[6].isdigit()
    assert info.model_year == 2003
    assert "1980-2009" in info.model_year_source


def test_year_heuristic_letter_char7_is_2010_plus():
    # Tesla: char 7 == 'E' (a letter) -> 2010+ cycle. Code 'H' -> 2017.
    info = decode_vin("5YJSA1E14HF000337")
    assert info.vin[6].isalpha()
    assert info.model_year == 2017
    assert "2010-2039" in info.model_year_source


def test_year_cycle_boundaries():
    # Two crafted VINs identical except char 7 (idx 6) and char 10 (year code 'A').
    # char 7 digit -> 1980 cycle; char 7 letter -> 2010 cycle.
    # Positions: idx6 = char 7, idx9 = char 10 (year code).
    letter_at_7 = list("1G1AAAAAAA0000000")  # 17 chars, char7 idx6 = 'A' (letter)
    letter_at_7[9] = "A"                      # year code 'A'
    digit_at_7 = list("1G1AAA1AAA0000000")   # char7 idx6 = '1' (digit)
    digit_at_7[9] = "A"                       # year code 'A'

    assert decode_vin("".join(digit_at_7)).model_year == 1980
    assert decode_vin("".join(letter_at_7)).model_year == 2010


# --------------------------------------------------------------------------- #
# Robustness — never raises
# --------------------------------------------------------------------------- #
def test_bad_length_collects_error():
    info = decode_vin("SHORT")
    assert isinstance(info, VinInfo)
    assert any("17 characters" in e for e in info.errors)
    assert not info.is_valid


def test_empty_string_does_not_raise():
    info = decode_vin("")
    assert isinstance(info, VinInfo)
    assert info.errors


def test_none_does_not_raise():
    info = decode_vin(None)  # type: ignore[arg-type]
    assert isinstance(info, VinInfo)
    assert info.errors


def test_illegal_letters_rejected():
    info = decode_vin("1HGCM8263IA004352")  # 'I' at position 10
    assert any("illegal letter" in e for e in info.errors)


def test_to_dict_and_str():
    info = decode_vin("1HGCM82633A004352")
    d = info.to_dict()
    assert d["manufacturer"] == "Honda"
    assert d["model_year"] == 2003
    assert "Honda" in str(info)
    assert "2003" in str(info)


def test_length_constant():
    assert VIN_LENGTH == 17
