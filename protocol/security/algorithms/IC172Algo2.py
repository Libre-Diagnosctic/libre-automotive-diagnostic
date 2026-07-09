"""IC172Algo2 — ported from jglim/UnlockECU.

Faithful Python port of ``IC172Algo2.cs`` (MIT, (c) 2020 JinGen Lim).
IC172 Level 113 (experimental): per-nibble signed lookups accumulated into a
32-bit key with nibble-position weighting.
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


class IC172Algo2(SecurityProvider):
    NAME = "IC172Algo2"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 4) or (key_length != 4):
            return None

        key_pool: List[List[int]] = []
        key_pool.append([0,   -1,  -2,  -3,  -4,  -5,  -6,  -7,  -8,  -9,  -10, -11, -12, -13, -14, -15])
        key_pool.append([251, 252, 253, 254, 255, 256, 257, 258, 243, 244, 245, 246, 247, 248, 249, 250])
        key_pool.append([0,   1,   -2,  -1,  4,   5,   2,   3,   8,   9,   6,   7,   12,  13,  10,  11])
        key_pool.append([73,  72,  75,  74,  69,  68,  71,  70,  81,  80,  83,  82,  77,  76,  79,  78])
        key_pool.append([0,   -1,  -2,  -3,  4,   3,   2,   1,   8,   7,   6,   5,   12,  11,  10,  9])
        key_pool.append([203, 202, 205, 204, 207, 206, 209, 208, 195, 194, 197, 196, 199, 198, 201, 200])
        key_pool.append([0,   1,   2,   3,   -4,  -3,  -2,  -1,  8,   9,   10,  11,  4,   5,   6,   7])
        key_pool.append([185, 184, 183, 182, 181, 180, 179, 178, 193, 192, 191, 190, 189, 188, 187, 186])

        nibbles = expand_nibbles(seed)
        key_result = 0  # C# int (32-bit signed), Python unbounded is fine pre-cast
        for i in range(8):
            key_result += key_pool[i][nibbles[i]] << ((7 - i) * 4)

        out_key = bytearray(4)
        out_key[0:4] = int_to_bytes(key_result & U32, BIG)  # C# (uint)key_result
        return bytes(out_key)
