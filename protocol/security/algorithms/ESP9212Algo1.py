"""ESP9212Algo1 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/ESP9212Algo1.cs (MIT, (c) 2020 JinGen Lim).
Experimental, unverified per the original comment.
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


class ESP9212Algo1(SecurityProvider):
    NAME = "ESP9212Algo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if key_length != 2:
            return None
        if len(seed) != 2:
            return None

        val = seed[0] & U32
        val = (val << 8) & U32
        val |= seed[1]

        snapshot = val
        val //= 4
        val ^= snapshot
        val = (val * 8) & U32
        val ^= snapshot

        out_key = bytearray(2)
        out_key[0] = (val >> 8) & 0xFF
        out_key[1] = val & 0xFF
        return bytes(out_key)
