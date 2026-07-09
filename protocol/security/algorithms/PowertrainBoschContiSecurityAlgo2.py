"""PowertrainBoschContiSecurityAlgo2 — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Faithful Python port of ``PowertrainBoschContiSecurityAlgo2.cs``. Appears specific
to MED97, SIM271CNG906.
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


class PowertrainBoschContiSecurityAlgo2(SecurityProvider):
    NAME = "PowertrainBoschContiSecurityAlgo2"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        table = param_bytes(parameters, "Table")
        uw_masc = param_bytes(parameters, "uwMasc")

        if len(seed) != 2 or key_length != 2:
            return None

        shift_index_a = 1
        shift_index_b = 1
        activated_bits = 0

        in_seed_as_int = (seed[1] | (seed[0] << 8)) & U32
        uw_masc_as_int = (uw_masc[1] | (uw_masc[0] << 8)) & U32

        for _ in range(16):
            if (shift_index_a & uw_masc_as_int) > 0:
                if (shift_index_a & in_seed_as_int) > 0:
                    activated_bits |= shift_index_b
                shift_index_b = (shift_index_b * 2) & U32
            shift_index_a = (shift_index_a * 2) & U32

        key_as_int = ((table[activated_bits] * in_seed_as_int) & U32) >> 8
        key_as_int &= 0xFFFF

        out_key = bytearray(2)
        out_key[0] = (key_as_int >> 8) & 0xFF
        out_key[1] = (key_as_int >> 0) & 0xFF
        return bytes(out_key)
