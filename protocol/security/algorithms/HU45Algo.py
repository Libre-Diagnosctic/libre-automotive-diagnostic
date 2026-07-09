"""HU45Algo seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/HU45Algo.cs (MIT, (c) 2020 JinGen Lim).
HU45Algo as found in HU45_hu45_sec_12_05_01, intended for level 7 (CBF).
The name is unofficial.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter, U32, BIG, LITTLE,
    param_byte, param_int, param_long, param_bytes,
    bytes_to_int, int_to_bytes, get_bit, set_bit, get_byte, set_byte,
    rotate_left, rotate_right, count_ones, expand_nibbles, collapse_nibbles,
    bytes_from_hex, bytes_to_hex, pad_bytes, memset,
)


class HU45Algo(SecurityProvider):
    NAME = "HU45Algo"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if len(seed) != 2 or key_length != 2:
            return None

        # C# int is signed 32-bit; ~x == -x - 1. Keep results as Python ints,
        # the (byte) casts below select the low 8 bits (two's-complement).
        partial = (~(seed[0] + (seed[1] << 8))) - 0x307

        out_key = bytearray(2)
        out_key[0] = (partial >> 8) & 0xFF
        out_key[1] = ((~seed[0]) - 7) & 0xFF
        return bytes(out_key)
