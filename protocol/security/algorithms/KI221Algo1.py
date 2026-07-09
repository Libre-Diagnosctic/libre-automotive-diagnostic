"""KI221Algo1 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/KI221Algo1.cs (MIT, (c) 2020 JinGen Lim).
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


class KI221Algo1(SecurityProvider):
    NAME = "KI221Algo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 8) or (key_length != 7):
            return None

        # In the original implementation, level is not used in the key computation
        level = param_byte(parameters, "Level")
        k = bytearray(param_bytes(parameters, "K"))
        root_key = bytes_to_int(k, BIG)

        k[0] ^= seed[6]
        k[1] ^= seed[4]
        k[2] ^= seed[2]
        k[3] ^= seed[0]

        rs = bytes_to_int(bytes([k[0], k[3], k[2], k[1]]), LITTLE)

        inter = (((rs << 29) & U32) + (rs >> 3)) & U32
        inter ^= root_key
        inter &= U32
        key = ((inter >> 25) + ((inter << 7) & U32)) & U32
        key_bytes = int_to_bytes(key, BIG)
        k[0] = key_bytes[0]
        k[1] = key_bytes[1]
        k[2] = key_bytes[2]
        k[3] = key_bytes[3]

        # Last 2 bytes are originally hardcoded as zeroes, other tools use FF.
        result = [level, k[0], k[3], k[2], k[1], 0, 0]

        out_key = bytearray(key_length)
        out_key[0:len(result)] = bytes(result)
        return bytes(out_key)
