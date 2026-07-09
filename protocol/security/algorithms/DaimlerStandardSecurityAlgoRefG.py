"""DaimlerStandardSecurityAlgoRefG — ported from jglim/UnlockECU.

Faithful Python port of ``DaimlerStandardSecurityAlgoRefG.cs`` (MIT, (c) 2020
JinGen Lim). Derivative of DaimlerStandardSecurityAlgoMod with four custom
constants (kA0, kA1, kC0, kC1) for the intermediate transformation.
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


class DaimlerStandardSecurityAlgoRefG(SecurityProvider):
    NAME = "DaimlerStandardSecurityAlgoRefG"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        crypto_key_bytes = param_bytes(parameters, "K_refG")
        crypto_key = bytes_to_int(crypto_key_bytes, BIG)

        kA_0 = 3040238857  # long
        kA_1 = 4126034881  # long
        kC_0 = 2094854071  # long
        kC_1 = 3555108353  # long

        if (len(seed) != 8) or (key_length != 4):
            return None

        seed_a = bytes_to_int(seed, BIG, 0)  # promoted to long
        seed_b = bytes_to_int(seed, BIG, 4)

        # C# 'long' is 64-bit signed; Python ints are unbounded so no masking here.
        intermediate1 = kA_0 * seed_a + kC_0
        intermediate2 = kA_1 * seed_b + kC_1
        seed_key = intermediate1 ^ intermediate2 ^ crypto_key

        out_key = bytearray(4)
        out_key[0:4] = int_to_bytes(seed_key & U32, BIG)  # C# (uint)seedKey
        return bytes(out_key)
