"""MarquardtSecurityAlgo — ported from jglim/UnlockECU.

Faithful Python port of ``MarquardtSecurityAlgo.cs`` (MIT, (c) 2020 JinGen
Lim). A simple modular-arithmetic seed/key transform using const_M, const_C
and const_A parameters.
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


class MarquardtSecurityAlgo(SecurityProvider):
    NAME = "MarquardtSecurityAlgo"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        const_m_bytes = param_bytes(parameters, "const_M")
        const_c_bytes = param_bytes(parameters, "const_C")
        const_a_bytes = param_bytes(parameters, "const_A")

        const_m = bytes_to_int(const_m_bytes, BIG)
        const_c = bytes_to_int(const_c_bytes, BIG)
        const_a = bytes_to_int(const_a_bytes, BIG)
        in_seed_as_int = bytes_to_int(seed, BIG)

        if (len(seed) != 4) or (key_length != 4):
            return None

        # C# 'unchecked': uint wraps mod 2^32. '%' binds tighter than '*' and '+'
        # in C#, so this is: constC + ((inSeedAsInt * constA) % constM).
        out_key_int = (const_c + ((in_seed_as_int * const_a) & U32) % const_m) & U32

        out_key = bytearray(4)
        out_key[0:4] = int_to_bytes(out_key_int, BIG)
        return bytes(out_key)
