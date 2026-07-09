"""SWSP177 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/SWSP177.cs (MIT, (c) 2020 JinGen Lim).
Behavior, param sizes don't match DLL per the original comment.
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


class SWSP177(SecurityProvider):
    NAME = "SWSP177"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        crypto_key_bytes = param_bytes(parameters, "KeyConst")
        crypto_key = bytes_to_int(crypto_key_bytes, BIG)

        if len(seed) != 4 or key_length != 4:
            return None

        # C# 'ulong seedA' — unbounded here, masked where cast to (uint) for output.
        seed_a = bytes_to_int(seed, BIG, 0)

        for _ in range(35):
            seed_a = ((seed_a >> 1) | ((seed_a & 1) * 0x80000000)) & 0xFFFFFFFFFFFFFFFF
            seed_a ^= crypto_key

        seed_key = seed_a & 0xFFFFFFFF

        out_key = bytearray(4)
        out_key[:] = int_to_bytes(seed_key & U32, BIG)
        return bytes(out_key)
