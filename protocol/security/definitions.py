"""ECU security definitions — loaded from ``assets/unlockecu_db.json``.

A faithful port of UnlockECU's ``Definition`` model and ``FindDefinition``. The
db.json ships verbatim from jglim/UnlockECU (MIT); it is reverse-engineered data
containing seed/key *parameters* (constants), not proprietary binaries.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from .provider import Parameter

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "unlockecu_db.json"


class Definition:
    """One ECU/level entry: which provider + parameters unlock a security level."""

    __slots__ = (
        "ecu_name", "aliases", "access_level", "seed_length",
        "key_length", "provider", "origin", "parameters",
    )

    def __init__(self, ecu_name, aliases, access_level, seed_length,
                 key_length, provider, origin, parameters):
        self.ecu_name = ecu_name
        self.aliases = aliases
        self.access_level = access_level
        self.seed_length = seed_length
        self.key_length = key_length
        self.provider = provider
        self.origin = origin
        self.parameters = parameters

    @classmethod
    def from_dict(cls, d: dict) -> "Definition":
        return cls(
            ecu_name=d.get("EcuName", ""),
            aliases=list(d.get("Aliases", []) or []),
            access_level=int(d.get("AccessLevel", -1)),
            seed_length=int(d.get("SeedLength", 0)),
            key_length=int(d.get("KeyLength", 0)),
            provider=d.get("Provider", ""),
            origin=d.get("Origin", ""),
            parameters=[Parameter.from_dict(p) for p in d.get("Parameters", []) or []],
        )

    def __repr__(self) -> str:
        return (f"Definition(ecu={self.ecu_name!r}, level={self.access_level}, "
                f"seed={self.seed_length}, key={self.key_length}, provider={self.provider!r})")


_DEFINITIONS: Optional[List[Definition]] = None


def load_definitions(path: Path = _DB_PATH) -> List[Definition]:
    """Load and cache all definitions from the JSON library."""
    global _DEFINITIONS
    if _DEFINITIONS is None:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:  # pragma: no cover - asset ships with repo
            raw = []
        _DEFINITIONS = [Definition.from_dict(d) for d in raw]
    return _DEFINITIONS


def find_definition(ecu_name: str, access_level: int,
                    definitions: Optional[List[Definition]] = None) -> Optional[Definition]:
    """Find the definition for an ECU name + access level (UnlockECU.FindDefinition).

    Matching mirrors the C#: the level must match, and the (upper-cased) input name
    must equal the stored ``EcuName`` (upper-cased) or appear in ``Aliases``.
    """
    defs = definitions if definitions is not None else load_definitions()
    key = ecu_name.upper()
    for d in defs:
        if access_level != d.access_level:
            continue
        if key == d.ecu_name.upper() or ecu_name in d.aliases or key in [a.upper() for a in d.aliases]:
            return d
    return None


def ecu_names() -> List[str]:
    """All distinct ECU names in the library (for UI pickers)."""
    return sorted({d.ecu_name for d in load_definitions()})
