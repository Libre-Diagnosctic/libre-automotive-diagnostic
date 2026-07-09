"""VIN decoder (ISO 3779 / ISO 3780 / NHTSA FMVSS 565).

A Vehicle Identification Number is 17 characters, split into three sections:

    WMI  chars 1-3   World Manufacturer Identifier   (who built it)
    VDS  chars 4-9   Vehicle Descriptor Section      (what it is; char 9 = check digit)
    VIS  chars 10-17 Vehicle Identifier Section       (char 10 = model year,
                                                        char 11 = plant,
                                                        chars 12-17 = serial)

The letters I, O and Q are never used, so they can never be confused with 1, 0.

This module is transport-agnostic: give :func:`decode_vin` the 17-character
string that :func:`protocol.obd2.read_vin` (or any other source) returned and it
hands back a fully populated :class:`VinInfo`. It never raises on bad input --
every problem is appended to ``VinInfo.errors`` instead, so a malformed VIN read
off a flaky bus still yields a usable, inspectable object.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

VIN_LENGTH = 17

# Letters that ISO 3779 forbids (visually ambiguous with 0/1).
ILLEGAL_LETTERS = frozenset("IOQ")

# --------------------------------------------------------------------------- #
# Check-digit transliteration (North American / FMVSS 565).
# Digits map to themselves; letters map per the standard table below.
# --------------------------------------------------------------------------- #
_TRANSLITERATION: dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
for _d in "0123456789":
    _TRANSLITERATION[_d] = int(_d)

# Positional weights, char 1..17. The check-digit position (char 9) has weight 0.
_CHECK_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)

# --------------------------------------------------------------------------- #
# Model-year code cycle (char 10). The alphabet skips I, O, Q, U, Z and the
# digit 0, giving a 30-year repeating cycle. It ran 1980->2009, then restarts
# with A=2010 and repeats every 30 years thereafter.
# --------------------------------------------------------------------------- #
_YEAR_CODES = (
    "ABCDEFGHJKLMNPRSTVWXY"   # 1980..2000  (21 codes)
    "123456789"               # 2001..2009  (9 codes)  -> 30-code cycle
)
assert len(_YEAR_CODES) == 30
_YEAR_INDEX = {c: i for i, c in enumerate(_YEAR_CODES)}


# --------------------------------------------------------------------------- #
# WMI -> manufacturer. Real 3-character WMIs. Where a maker owns a whole
# prefix range the common assignments are listed explicitly. Unknown WMIs fall
# back to region/country (see _REGION_TABLE) with manufacturer=None.
# --------------------------------------------------------------------------- #
_WMI_MANUFACTURER: dict[str, str] = {
    # ---- Ford ----
    "1FA": "Ford", "1FB": "Ford", "1FC": "Ford", "1FD": "Ford",
    "1FM": "Ford", "1FT": "Ford", "2FA": "Ford", "2FM": "Ford",
    "2FT": "Ford", "3FA": "Ford", "3FE": "Ford", "WF0": "Ford",
    "WF1": "Ford", "6FP": "Ford", "MAJ": "Ford", "NM0": "Ford",
    "LFA": "Ford",
    # ---- Lincoln / Mercury ----
    "5LM": "Lincoln", "1LN": "Lincoln", "4M2": "Mercury", "1ME": "Mercury",
    # ---- General Motors (Chevrolet / GMC / Buick / Cadillac / Pontiac / Saturn) ----
    "1G1": "Chevrolet", "1GC": "Chevrolet", "1GB": "Chevrolet",
    "1GN": "Chevrolet", "2G1": "Chevrolet", "3G1": "Chevrolet",
    "3GN": "Chevrolet", "KL1": "Chevrolet", "1GT": "GMC", "1GK": "GMC",
    "1GD": "GMC", "1G4": "Buick", "1G6": "Cadillac", "1GY": "Cadillac",
    "1G2": "Pontiac", "1G8": "Saturn", "5GA": "Buick", "6G1": "Holden",
    "6G2": "Pontiac", "6H8": "Holden", "JG1": "Chevrolet",
    # ---- Chrysler / Dodge / Jeep / RAM / Stellantis NA ----
    "1C3": "Chrysler", "1C4": "Chrysler", "1C6": "Chrysler",
    "2C3": "Chrysler", "3C3": "Chrysler", "3C4": "Chrysler",
    "1B3": "Dodge", "2B3": "Dodge", "1D4": "Dodge", "1D7": "Dodge",
    "2D4": "Dodge", "3D7": "Dodge", "1J4": "Jeep", "1J8": "Jeep",
    "1C7": "RAM", "3C6": "RAM",
    # ---- Toyota / Lexus / Scion ----
    "JT2": "Toyota", "JT3": "Toyota", "JT4": "Toyota", "JTD": "Toyota",
    "JTE": "Toyota", "JTF": "Toyota", "JTG": "Toyota", "JTH": "Lexus",
    "JTJ": "Lexus", "JTK": "Toyota", "JTL": "Toyota", "JTM": "Toyota",
    "JTN": "Toyota", "4T1": "Toyota", "4T3": "Toyota", "4T4": "Toyota",
    "5TB": "Toyota", "5TD": "Toyota", "5TE": "Toyota", "5TF": "Toyota",
    "2T1": "Toyota", "2T2": "Lexus", "MR0": "Toyota", "SB1": "Toyota",
    "6T1": "Toyota", "NMT": "Toyota",
    # ---- Honda / Acura ----
    "1HG": "Honda", "2HG": "Honda", "3HG": "Honda", "1HF": "Honda",
    "JHM": "Honda", "JHL": "Honda", "JHG": "Honda", "SHH": "Honda",
    "SHS": "Honda", "2HK": "Honda", "5FN": "Honda", "5FP": "Honda",
    "5J6": "Honda", "5KB": "Honda", "19X": "Honda", "19U": "Acura",
    "JH4": "Acura", "19V": "Acura", "2HH": "Acura",
    # ---- Nissan / Infiniti / Datsun ----
    "JN1": "Nissan", "JN6": "Nissan", "JN8": "Nissan", "1N4": "Nissan",
    "1N6": "Nissan", "3N1": "Nissan", "3N6": "Nissan", "5N1": "Nissan",
    "5BB": "Nissan", "VSK": "Nissan", "JNK": "Infiniti", "JNR": "Infiniti",
    "JNX": "Infiniti", "5N3": "Infiniti",
    # ---- Volkswagen ----
    "WVW": "Volkswagen", "WV1": "Volkswagen", "WV2": "Volkswagen",
    "WVG": "Volkswagen", "1VW": "Volkswagen", "3VW": "Volkswagen",
    "9BW": "Volkswagen", "AAV": "Volkswagen", "8AW": "Volkswagen",
    # ---- Audi ----
    "WAU": "Audi", "WA1": "Audi", "WUA": "Audi", "TRU": "Audi",
    "93U": "Audi",
    # ---- BMW ----
    "WBA": "BMW", "WBS": "BMW", "WBX": "BMW", "WBY": "BMW",
    "4US": "BMW", "5UX": "BMW", "5UM": "BMW", "WB1": "BMW (motorrad)",
    "WB4": "BMW", "NM4": "BMW",
    # ---- MINI ----
    "WMW": "MINI",
    # ---- Mercedes-Benz ----
    "WDB": "Mercedes-Benz", "WDC": "Mercedes-Benz", "WDD": "Mercedes-Benz",
    "WDF": "Mercedes-Benz", "W1K": "Mercedes-Benz", "W1N": "Mercedes-Benz",
    "W1V": "Mercedes-Benz", "4JG": "Mercedes-Benz", "55S": "Mercedes-Benz",
    "WMX": "Mercedes-AMG", "WME": "Smart",
    # ---- Hyundai ----
    "KMH": "Hyundai", "KMF": "Hyundai", "KMJ": "Hyundai",
    "5NP": "Hyundai", "5NM": "Hyundai", "TMA": "Hyundai", "NLH": "Hyundai",
    # ---- Kia ----
    "KNA": "Kia", "KNB": "Kia", "KND": "Kia", "KNE": "Kia",
    "KNM": "Kia", "5XY": "Kia", "5XX": "Kia", "3KP": "Kia", "U5Y": "Kia",
    # ---- Genesis ----
    "KMT": "Genesis",
    # ---- Volvo ----
    "YV1": "Volvo", "YV4": "Volvo", "YV5": "Volvo", "7JR": "Volvo",
    "LVY": "Volvo", "YB1": "Volvo Trucks", "YV2": "Volvo Trucks",
    # ---- Subaru ----
    "JF1": "Subaru", "JF2": "Subaru", "JF3": "Subaru", "4S3": "Subaru",
    "4S4": "Subaru", "4S6": "Subaru",
    # ---- Mazda ----
    "JM1": "Mazda", "JM3": "Mazda", "JM6": "Mazda", "JM7": "Mazda",
    "4F2": "Mazda", "4F4": "Mazda", "1YV": "Mazda", "3MZ": "Mazda",
    "3MV": "Mazda", "JMZ": "Mazda",
    # ---- Mitsubishi ----
    "JA3": "Mitsubishi", "JA4": "Mitsubishi", "JA7": "Mitsubishi",
    "4A3": "Mitsubishi", "4A4": "Mitsubishi", "6MM": "Mitsubishi",
    "ML0": "Mitsubishi", "MMB": "Mitsubishi", "MMT": "Mitsubishi",
    # ---- Suzuki ----
    "JS1": "Suzuki (motorcycle)", "JS2": "Suzuki", "JS3": "Suzuki",
    "KL5": "Suzuki", "MA3": "Suzuki", "TSM": "Suzuki",
    # ---- Isuzu ----
    "JAA": "Isuzu", "JAB": "Isuzu", "JAL": "Isuzu", "4NU": "Isuzu",
    "4NG": "Isuzu",
    # ---- Daihatsu ----
    "JDA": "Daihatsu",
    # ---- Tesla ----
    "5YJ": "Tesla", "7SA": "Tesla", "7G2": "Tesla", "XP7": "Tesla",
    "LRW": "Tesla",
    # ---- Porsche ----
    "WP0": "Porsche", "WP1": "Porsche", "WP2": "Porsche",
    # ---- Land Rover / Jaguar ----
    "SAL": "Land Rover", "SAJ": "Jaguar", "SAD": "Jaguar (Daimler)",
    "SAR": "Rover",
    # ---- Renault ----
    "VF1": "Renault", "VF2": "Renault", "VF6": "Renault (RVI truck)",
    "93Y": "Renault", "8A1": "Renault", "VNV": "Renault",
    # ---- Dacia ----
    "UU1": "Dacia", "UU6": "Dacia",
    # ---- Peugeot ----
    "VF3": "Peugeot", "8AD": "Peugeot", "936": "Peugeot",
    # ---- Citroen ----
    "VF7": "Citroen", "VS7": "Citroen (Spain)",
    # ---- DS ----
    "VR1": "DS Automobiles",
    # ---- Opel / Vauxhall ----
    "W0L": "Opel", "W0V": "Opel", "SED": "Vauxhall",
    # ---- Fiat / Alfa Romeo / Lancia / Abarth ----
    "ZFA": "Fiat", "ZFC": "Fiat",
    "ZAR": "Alfa Romeo", "ZLA": "Lancia", "ZAM": "Maserati",
    # ---- Ferrari / Lamborghini / other exotica ----
    "ZFF": "Ferrari", "ZHW": "Lamborghini", "ZA9": "Lamborghini",
    "SCF": "Aston Martin", "SCB": "Bentley", "SCC": "Lotus",
    "SCA": "Rolls-Royce", "SCE": "DeLorean", "SCG": "Koenigsegg",
    "ZAP": "Piaggio", "ZAA": "Autobianchi", "ZGU": "Moto Guzzi",
    # ---- SEAT / Skoda ----
    "VSS": "SEAT", "TMB": "Skoda", "TMP": "Skoda",
    # ---- Saab ----
    "YS3": "Saab", "YS4": "Saab (Scania trucks)",
    # ---- Scania / MAN / Iveco (EU trucks) ----
    "XLE": "Scania", "WMA": "MAN", "ZCF": "Iveco", "WJM": "Iveco",
    "WDA": "Mercedes-Benz (trucks)",
    # ---- North American heavy trucks ----
    "1XK": "Kenworth", "1XP": "Peterbilt", "2NP": "Peterbilt",
    "1NP": "Peterbilt", "1FU": "Freightliner", "1FV": "Freightliner",
    "3AK": "Freightliner", "4V4": "Volvo Trucks", "4V2": "Volvo Trucks",
    "1M1": "Mack", "1M2": "Mack", "5KK": "Hino", "JHB": "Hino",
    "1HT": "International/Navistar", "3HA": "International/Navistar",
    "2HS": "International/Navistar", "1NK": "Kenworth",
    # ---- Buses / RV / other NA ----
    "4UZ": "Freightliner (chassis)", "1BA": "Blue Bird",
    # ---- Chinese makes ----
    "LFV": "FAW-Volkswagen", "LFM": "FAW", "LGB": "Dongfeng/Nissan",
    "LSV": "SAIC Volkswagen", "LSY": "Brilliance", "LVV": "Chery",
    "LVS": "Ford (Changan)", "LGX": "BYD", "LGW": "Great Wall",
    "LJD": "Dongfeng", "LB2": "Geely", "L6T": "Geely", "LZW": "SAIC-GM-Wuling",
    "LYV": "Volvo (China)", "LRB": "Buick (SGM)", "LNB": "BMW Brilliance",
    "LZG": "Shaanxi", "LFB": "FAW", "LGH": "Dongfeng", "LDC": "Dongfeng Peugeot",
    "LVR": "Mazda (Changan)", "LSG": "SAIC-GM (Buick)", "LFN": "FAW",
    # ---- Indian makes ----
    "MAT": "Tata Motors", "MA1": "Mahindra", "MA6": "GM India",
    "MBH": "Maruti Suzuki", "MB1": "Ashok Leyland", "MAK": "Honda India",
    "MAL": "Hyundai India", "MAB": "Volkswagen India", "MAC": "Tata",
    "ME4": "Honda (motorcycle India)",
    # ---- Australian / Oceania (6-7 range) ----
    "6MP": "Ford Australia", "6H8": "Holden",
    "7A3": "Trackmaster (NZ)", "6AB": "MG Australia",
    # ---- South American ----
    "9BW": "Volkswagen", "9BD": "Fiat (Brazil)", "9BG": "Chevrolet (Brazil)",
    "9BF": "Ford (Brazil)", "9BR": "Toyota (Brazil)", "9BM": "Mercedes-Benz (Brazil)",
    "8AP": "Fiat (Argentina)", "8AG": "Chevrolet (Argentina)",
    "8AF": "Ford (Argentina)", "8AK": "Suzuki (Argentina)",
    "93H": "Honda (Brazil)", "93X": "Mitsubishi (Brazil)",
    # ---- Other Japanese ----
    "JYA": "Yamaha", "JKA": "Kawasaki", "JKB": "Kawasaki",
    # ---- Ukraine / Russia / East Europe ----
    "Y6D": "ZAZ", "XTA": "Lada/AvtoVAZ", "XW8": "Volkswagen (Russia)",
    "X4X": "BMW (Russia)", "Z94": "Hyundai (Russia)", "XW7": "Toyota (Russia)",
    # ---- Korea additional ----
    "KPT": "SsangYong", "KPA": "SsangYong", "KL3": "GM Korea",
    "KLA": "Daewoo", "KLY": "Daewoo",
}


# --------------------------------------------------------------------------- #
# Region + country from WMI. ISO 3780 partitions the first character into
# geographic ranges; the second character narrows the country. We resolve the
# most-specific 2-char prefix rule first, then fall back to the 1-char region.
#
# Each entry: (predicate, region, country). Two-char rules are checked before
# one-char rules by ordering. ``None`` country means "region only, unspecified".
# --------------------------------------------------------------------------- #

# Fine-grained 2-character country ranges (checked first).
_COUNTRY_2CHAR: list[tuple[str, str, str, str]] = [
    # (start2, end2, region, country) inclusive on the 2-char prefix
    ("AA", "AH", "Africa", "South Africa"),
    ("AJ", "AN", "Africa", "Ivory Coast"),
    ("AP", "A0", "Africa", "not assigned"),
    ("BA", "BE", "Africa", "Angola"),
    ("BF", "BK", "Africa", "Kenya"),
    ("BL", "BR", "Africa", "Tanzania"),
    ("CA", "CE", "Africa", "Benin"),
    ("CF", "CK", "Africa", "Madagascar"),
    ("CL", "CR", "Africa", "Tunisia"),
    ("DA", "DE", "Africa", "Egypt"),
    ("DF", "DK", "Africa", "Morocco"),
    ("DL", "DR", "Africa", "Zambia"),
    ("EA", "EE", "Africa", "Ethiopia"),
    ("EF", "EK", "Africa", "Mozambique"),
    ("FA", "FE", "Africa", "Ghana"),
    ("FF", "FK", "Africa", "Nigeria"),
    # Asia
    ("JA", "J0", "Asia", "Japan"),
    ("KA", "KE", "Asia", "Sri Lanka"),
    ("KF", "KK", "Asia", "Israel"),
    ("KL", "KR", "Asia", "South Korea"),
    ("KS", "K0", "Asia", "Kazakhstan"),
    ("LA", "L0", "Asia", "China"),
    ("MA", "ME", "Asia", "India"),
    ("MF", "MK", "Asia", "Indonesia"),
    ("ML", "MR", "Asia", "Thailand"),
    ("MS", "M0", "Asia", "Myanmar"),
    ("NA", "NE", "Asia", "Iran"),
    ("NF", "NK", "Asia", "Pakistan"),
    ("NL", "NR", "Asia", "Turkey"),
    ("PA", "PE", "Asia", "Philippines"),
    ("PF", "PK", "Asia", "Singapore"),
    ("PL", "PR", "Asia", "Malaysia"),
    ("RA", "RE", "Asia", "United Arab Emirates"),
    ("RF", "RK", "Asia", "Taiwan"),
    ("RL", "RR", "Asia", "Vietnam"),
    ("RS", "R0", "Asia", "Saudi Arabia"),
    # Europe
    ("SA", "SM", "Europe", "United Kingdom"),
    ("SN", "ST", "Europe", "Germany"),
    ("SU", "SZ", "Europe", "Poland"),
    ("TA", "TH", "Europe", "Switzerland"),
    ("TJ", "TP", "Europe", "Czech Republic"),
    ("TR", "TV", "Europe", "Hungary"),
    ("TW", "T1", "Europe", "Portugal"),
    ("UH", "UM", "Europe", "Denmark"),
    ("UN", "UT", "Europe", "Ireland"),
    ("UU", "UZ", "Europe", "Romania"),
    ("U5", "U7", "Asia", "South Korea"),
    ("VA", "VE", "Europe", "Austria"),
    ("VF", "VR", "Europe", "France"),
    ("VS", "VW", "Europe", "Spain"),
    ("VX", "V2", "Europe", "Serbia"),
    ("V3", "V5", "Europe", "Croatia"),
    ("V6", "V0", "Europe", "Estonia"),
    ("WA", "W0", "Europe", "Germany"),
    ("XA", "XE", "Europe", "Bulgaria"),
    ("XF", "XK", "Europe", "Greece"),
    ("XL", "XR", "Europe", "Netherlands"),
    ("XS", "XW", "Europe", "USSR/CIS"),
    ("XX", "X2", "Europe", "Luxembourg"),
    ("X3", "X0", "Europe", "Russia"),
    ("YA", "YE", "Europe", "Belgium"),
    ("YF", "YK", "Europe", "Finland"),
    ("YL", "YR", "Europe", "Sweden"),
    ("YS", "YW", "Europe", "Norway"),
    ("YX", "Y2", "Europe", "Belarus"),
    ("Y3", "Y0", "Europe", "Ukraine"),
    ("ZA", "ZR", "Europe", "Italy"),
    ("ZX", "Z2", "Europe", "Slovenia"),
    ("Z3", "Z5", "Europe", "Lithuania"),
    ("Z6", "Z0", "Europe", "Russia"),
    # North America
    ("1A", "10", "North America", "United States"),
    ("2A", "20", "North America", "Canada"),
    ("3A", "3W", "North America", "Mexico"),
    ("3X", "37", "North America", "Costa Rica"),
    ("38", "30", "North America", "Cayman Islands"),
    ("4A", "40", "North America", "United States"),
    ("5A", "50", "North America", "United States"),
    ("6A", "6W", "Oceania", "Australia"),
    ("7A", "7E", "Oceania", "New Zealand"),
    # South America
    ("8A", "8E", "South America", "Argentina"),
    ("8F", "8K", "South America", "Chile"),
    ("8L", "8R", "South America", "Ecuador"),
    ("8S", "8W", "South America", "Peru"),
    ("8X", "82", "South America", "Venezuela"),
    ("9A", "9E", "South America", "Brazil"),
    ("9F", "9K", "South America", "Colombia"),
    ("9L", "9R", "South America", "Paraguay"),
    ("9S", "9W", "South America", "Uruguay"),
    ("9X", "92", "South America", "Trinidad and Tobago"),
    ("93", "99", "South America", "Brazil"),
]

# Coarse 1-character regions (fallback).
_REGION_1CHAR: dict[str, str] = {
    "1": "North America", "2": "North America", "3": "North America",
    "4": "North America", "5": "North America",
    "6": "Oceania", "7": "Oceania",
    "8": "South America", "9": "South America", "0": "South America",
    "A": "Africa", "B": "Africa", "C": "Africa", "D": "Africa",
    "E": "Africa", "F": "Africa", "G": "Africa", "H": "Africa",
    "J": "Asia", "K": "Asia", "L": "Asia", "M": "Asia", "N": "Asia",
    "P": "Asia", "R": "Asia",
    "S": "Europe", "T": "Europe", "U": "Europe", "V": "Europe",
    "W": "Europe", "X": "Europe", "Y": "Europe", "Z": "Europe",
}


def _char_ord(c: str) -> int:
    """Order VIN chars A..Z then 0..9 so ranges like ('SA','SM') work by value."""
    if c.isdigit():
        return ord("Z") + 1 + int(c)
    return ord(c)


def _in_range(prefix2: str, start: str, end: str) -> bool:
    """True if 2-char ``prefix2`` falls within [start, end] on VIN char ordering.

    The first char must match exactly; the second char is range-compared. This
    mirrors how ISO 3780 assigns country blocks along the second character.
    """
    if prefix2[0] != start[0] or start[0] != end[0]:
        return False
    return _char_ord(start[1]) <= _char_ord(prefix2[1]) <= _char_ord(end[1])


def _lookup_region_country(wmi: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve (region, country) from a 3-char WMI via ISO 3780 ranges."""
    if not wmi:
        return None, None
    prefix2 = wmi[:2]
    if len(prefix2) == 2:
        for start, end, region, country in _COUNTRY_2CHAR:
            if _in_range(prefix2, start, end):
                return region, country
    region = _REGION_1CHAR.get(wmi[0])
    return region, None


# --------------------------------------------------------------------------- #
# Public data model
# --------------------------------------------------------------------------- #
@dataclass
class VinInfo:
    """Decoded VIN. Always constructed; problems live in :attr:`errors`."""

    vin: str
    wmi: Optional[str] = None
    vds: Optional[str] = None
    vis: Optional[str] = None
    manufacturer: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    model_year: Optional[int] = None
    model_year_source: Optional[str] = None
    plant_code: Optional[str] = None
    serial_number: Optional[str] = None
    check_digit: Optional[str] = None
    valid_check_digit: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when the VIN parsed cleanly (no structural errors collected)."""
        return not self.errors

    def to_dict(self) -> dict:
        """Plain-dict view (JSON friendly)."""
        return asdict(self)

    def __str__(self) -> str:
        make = self.manufacturer or "unknown make"
        year = self.model_year or "????"
        loc = self.country or self.region or "unknown origin"
        cd = "ok" if self.valid_check_digit else "unverified"
        base = f"{self.vin}: {year} {make} ({loc}) [check digit {cd}]"
        if self.errors:
            base += f"  !! {len(self.errors)} problem(s): " + "; ".join(self.errors)
        return base


# --------------------------------------------------------------------------- #
# Core computations
# --------------------------------------------------------------------------- #
def compute_check_digit(vin: str) -> Optional[str]:
    """Return the FMVSS 565 check digit ('0'..'9' or 'X') for a 17-char VIN.

    Returns ``None`` if any character is not transliteratable (should not happen
    after :func:`decode_vin` validation, but keeps this helper standalone).
    """
    if len(vin) != VIN_LENGTH:
        return None
    total = 0
    for ch, weight in zip(vin.upper(), _CHECK_WEIGHTS):
        value = _TRANSLITERATION.get(ch)
        if value is None:
            return None
        total += value * weight
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def _resolve_model_year(vin: str) -> tuple[Optional[int], Optional[str]]:
    """Resolve model year from char 10, disambiguating the 30-year cycle.

    Heuristic (industry standard for cars / light trucks): the year code repeats
    every 30 years, so e.g. 'A' could be 1980 or 2010. We use char 7 to pick the
    era -- if char 7 is a DIGIT the VIN belongs to the 1980-2009 cycle, and if it
    is a LETTER it belongs to the 2010+ cycle. Returns (year, human-readable rule).
    """
    code = vin[9].upper()
    idx = _YEAR_INDEX.get(code)
    if idx is None:
        return None, f"char 10 '{vin[9]}' is not a valid year code"

    char7 = vin[6].upper()
    if char7.isdigit():
        year = 1980 + idx
        rule = "char 7 is a digit -> 1980-2009 cycle"
    else:
        year = 2010 + idx
        rule = "char 7 is a letter -> 2010-2039 cycle"
    return year, rule


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def decode_vin(vin: str) -> VinInfo:
    """Decode ``vin`` into a :class:`VinInfo`. Never raises; see ``.errors``.

    Lowercase input is accepted and normalised to uppercase. Length and the
    forbidden letters I/O/Q are validated. Fields that cannot be derived are
    left ``None`` and the reason is appended to ``errors``.
    """
    raw = "" if vin is None else str(vin)
    normalized = raw.strip().upper()
    info = VinInfo(vin=normalized)

    # ---- length ----
    if len(normalized) != VIN_LENGTH:
        info.errors.append(
            f"VIN must be {VIN_LENGTH} characters, got {len(normalized)}"
        )
        # Still fill what we can from any leading characters.
        if len(normalized) >= 3:
            info.wmi = normalized[:3]
            info.manufacturer = _WMI_MANUFACTURER.get(info.wmi)
            info.region, info.country = _lookup_region_country(info.wmi)
        return info

    # ---- illegal characters ----
    bad = sorted({c for c in normalized if c in ILLEGAL_LETTERS})
    if bad:
        info.errors.append(
            "VIN contains illegal letter(s) " + ", ".join(bad) + " (I, O, Q are not allowed)"
        )
    non_alnum = sorted({c for c in normalized if not c.isalnum()})
    if non_alnum:
        info.errors.append("VIN contains non-alphanumeric character(s): " + ", ".join(non_alnum))

    # ---- sections ----
    info.wmi = normalized[0:3]
    info.vds = normalized[3:9]
    info.vis = normalized[9:17]
    info.check_digit = normalized[8]
    info.plant_code = normalized[10]
    info.serial_number = normalized[11:17]

    # ---- manufacturer + geography ----
    info.manufacturer = _WMI_MANUFACTURER.get(info.wmi)
    info.region, info.country = _lookup_region_country(info.wmi)
    if info.manufacturer is None:
        where = info.country or info.region or "unknown origin"
        info.errors.append(
            f"WMI '{info.wmi}' not in manufacturer table; origin inferred as {where}"
        )

    # ---- check digit ----
    expected = compute_check_digit(normalized)
    if expected is None:
        info.valid_check_digit = False
        info.errors.append("check digit could not be computed (untranslatable character)")
    else:
        info.valid_check_digit = expected == info.check_digit
        if not info.valid_check_digit:
            info.errors.append(
                f"check digit mismatch: char 9 is '{info.check_digit}', expected '{expected}' "
                "(note: only North American VINs are required to carry a valid check digit)"
            )

    # ---- model year ----
    info.model_year, info.model_year_source = _resolve_model_year(normalized)
    if info.model_year is None and info.model_year_source:
        info.errors.append(info.model_year_source)

    return info


__all__ = [
    "VinInfo",
    "decode_vin",
    "compute_check_digit",
    "VIN_LENGTH",
    "ILLEGAL_LETTERS",
]
