"""Diagnostic Trouble Code codec (SAE J2012 / ISO 15031-6).

A DTC is two bytes on the wire:

    bit 15-14 : category   0=P (powertrain) 1=C (chassis) 2=B (body) 3=U (network)
    bit 13-12 : first digit 0..3
    bit 11-8  : second digit (hex 0..F)
    bit 7-0   : third + fourth digits (hex)

So ``0x01 0x34`` decodes to ``"P0134"``. This binary form is what SocketCAN
sees directly; the ELM327 backend produces the same codes from its ASCII output.
"""
from __future__ import annotations

_CATEGORY = ("P", "C", "B", "U")
_CATEGORY_INDEX = {c: i for i, c in enumerate(_CATEGORY)}


def decode_dtc(hi: int, lo: int) -> str:
    """Decode a 2-byte DTC into its display code, e.g. ``(0x01, 0x34) -> "P0134"``."""
    prefix = _CATEGORY[(hi & 0xC0) >> 6]
    first = (hi & 0x30) >> 4
    return f"{prefix}{first}{hi & 0x0F:X}{lo:02X}"


def encode_dtc(code: str) -> bytes:
    """Encode a display code back to 2 bytes, e.g. ``"P0134" -> b"\\x01\\x34"``.

    Inverse of :func:`decode_dtc`; used by the simulator and round-trip tests.
    """
    cat = _CATEGORY_INDEX[code[0].upper()]
    first = int(code[1], 16)
    rest = int(code[2:], 16)
    value = (cat << 14) | (first << 12) | rest
    return bytes([(value >> 8) & 0xFF, value & 0xFF])
