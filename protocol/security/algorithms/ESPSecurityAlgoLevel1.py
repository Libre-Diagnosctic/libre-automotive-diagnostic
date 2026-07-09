"""ESPSecurityAlgoLevel1 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/ESPSecurityAlgoLevel1.cs (MIT, (c) 2020 JinGen Lim).
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


class ESPSecurityAlgoLevel1(SecurityProvider):
    NAME = "ESPSecurityAlgoLevel1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if len(seed) != 2 or key_length != 2:
            return None

        seed_as_int = (seed[1] | ((seed[0] & U32) << 8)) & U32
        key = ((4 * (((seed_as_int >> 3) ^ seed_as_int) & U32)) & U32) ^ seed_as_int
        key &= U32

        out_key = bytearray(2)
        out_key[0] = (key >> 8) & 0xFF
        out_key[1] = (key >> 0) & 0xFF
        return bytes(out_key)
