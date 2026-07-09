"""KI221Algo2 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/KI221Algo2.cs (MIT, (c) 2020 JinGen Lim).

Observed V850E2 pattern: (x ^ 0x78253947) + 0x83249272
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


class KI221Algo2(SecurityProvider):
    NAME = "KI221Algo2"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 4) or (key_length != 4):
            return None

        xor_bytes = param_bytes(parameters, "Xor")
        add_bytes = param_bytes(parameters, "Add")
        xor = bytes_to_int(xor_bytes, LITTLE)   # Almost always 0x78253947
        add = bytes_to_int(add_bytes, LITTLE)   # Almost always 0x83249272
        seed_val = bytes_to_int(seed, BIG)

        seed_val ^= xor
        seed_val = (seed_val + add) & U32

        out_key = bytearray(int_to_bytes(seed_val, BIG))
        return bytes(out_key)
