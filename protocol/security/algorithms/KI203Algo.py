"""KI203Algo seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/KI203Algo.cs (MIT, (c) 2020 JinGen Lim).
Collaborative effort by @rumator, Sergey (@Feezex) and Vladyslav Lupashevskyi
(@VladLupashevskyi): https://github.com/jglim/UnlockECU/issues/30
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


class KI203Algo(SecurityProvider):
    NAME = "KI203Algo"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 4) or (key_length != 4):
            return None

        root = bytes_to_int(param_bytes(parameters, "K"), BIG)
        ones = count_ones(root)

        val = (
            (seed[2] << 0) |
            (seed[0] << 8) |
            (seed[3] << 16) |
            (seed[1] << 24)
        ) & U32

        val = rotate_left(val, 3)
        val ^= root
        val = rotate_right(val, ones)

        out_key = bytearray(key_length)
        out_key[0] = get_byte(val, 0)
        out_key[1] = get_byte(val, 2)
        out_key[2] = get_byte(val, 3)
        out_key[3] = get_byte(val, 1)
        return bytes(out_key)
