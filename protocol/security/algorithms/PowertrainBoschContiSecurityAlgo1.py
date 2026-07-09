"""PowertrainBoschContiSecurityAlgo1 — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Faithful Python port of ``PowertrainBoschContiSecurityAlgo1.cs``. Appears specific
to MED97.
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


class PowertrainBoschContiSecurityAlgo1(SecurityProvider):
    NAME = "PowertrainBoschContiSecurityAlgo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        ub_table = param_bytes(parameters, "ubTable")
        mask = param_bytes(parameters, "Mask")

        if len(seed) != 2 or key_length != 2:
            return None

        in_seed_as_int = (seed[1] | (seed[0] << 8)) & U32
        mask_as_int = (mask[1] | (mask[0] << 8)) & U32

        sw_bit1 = (in_seed_as_int & mask_as_int & 0x4000) >> 12
        sw_bit2 = (in_seed_as_int & mask_as_int & 0x200) >> 8
        sw_bit3 = (in_seed_as_int & mask_as_int & 0x100) >> 8

        key_as_int = (ub_table[sw_bit1 | sw_bit2 | sw_bit3] * in_seed_as_int) & U32

        out_key = bytearray(2)
        out_key[0] = (key_as_int >> 16) & 0xFF
        out_key[1] = (key_as_int >> 8) & 0xFF
        return bytes(out_key)
