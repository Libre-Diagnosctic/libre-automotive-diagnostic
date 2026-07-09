"""IC172Algo1 — ported from jglim/UnlockECU.

Faithful Python port of ``IC172Algo1.cs`` (MIT, (c) 2020 JinGen Lim).
IC172 Level 7 (experimental): a key-pool / transposition-table lookup over
expanded seed nibbles, with a fixed personalization suffix.
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


class IC172Algo1(SecurityProvider):
    NAME = "IC172Algo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 8) or (key_length != 8):
            return None

        seed_input = bytes([seed[0], seed[2], seed[4], seed[6]])
        seed_input = expand_nibbles(seed_input)

        key_pool: List[bytes] = []
        key_pool.append(bytes([0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01]))
        key_pool.append(bytes([0x45, 0x67, 0x01, 0x23, 0xCD, 0xEF, 0x89, 0xAB]))
        key_pool.append(bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF]))
        key_pool.append(bytes([0x89, 0xAB, 0xCD, 0xEF, 0x01, 0x23, 0x45, 0x67]))
        key_pool.append(bytes([0x54, 0x76, 0x10, 0x32, 0xDC, 0xFE, 0x98, 0xBA]))
        key_pool.append(bytes([0xEF, 0xCD, 0xAB, 0x89, 0x67, 0x45, 0x23, 0x01]))
        key_pool.append(bytes([0x89, 0xAB, 0xCD, 0xEF, 0x01, 0x23, 0x45, 0x67]))
        key_pool.append(bytes([0xBA, 0x98, 0xFE, 0xDC, 0x32, 0x10, 0x76, 0x54]))

        transposition_table = bytes([5, 2, 7, 4, 1, 6, 3, 0])
        intermediate_key = bytearray(8)

        for i in range(len(transposition_table)):
            intermediate_key[i] = expand_nibbles(key_pool[i])[seed_input[transposition_table[i]]]

        # The suffix does not affect key generation; it is a personalization tag.
        suffix = bytes([0x55, 0x45, 0x43, 0x55])

        assembled_key = collapse_nibbles(bytes(intermediate_key))

        out_key = bytearray(8)
        out_key[0:4] = assembled_key[0:4]
        out_key[4:8] = suffix[0:4]
        return bytes(out_key)
