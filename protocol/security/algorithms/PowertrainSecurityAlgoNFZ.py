"""PowertrainSecurityAlgoNFZ — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Faithful Python port of ``PowertrainSecurityAlgoNFZ.cs``. Similar to
PowertrainDelphiSecurityAlgo, differing only in the bit selections that drive the
D/G value lookups.
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


class PowertrainSecurityAlgoNFZ(SecurityProvider):
    NAME = "PowertrainSecurityAlgoNFZ"

    @staticmethod
    def _create_d_value(bit2_enabled: int, bit1_enabled: int, bit0_enabled: int,
                        matrix: List[bytes]) -> int:
        i = 0
        j = 0
        if bit0_enabled != 0:
            j = set_bit(j, 0)
        if bit1_enabled != 0:
            j = set_bit(j, 1)
        if bit2_enabled != 0:
            j = set_bit(j, 2)
        i = set_byte(i, matrix[j][3], 0)
        i = set_byte(i, matrix[j][2], 1)
        i = set_byte(i, matrix[j][1], 2)
        i = set_byte(i, matrix[j][0], 3)
        return i & U32

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        d_value_matrix = [
            param_bytes(parameters, "D_VALUE_0"),
            param_bytes(parameters, "D_VALUE_1"),
            param_bytes(parameters, "D_VALUE_2"),
            param_bytes(parameters, "D_VALUE_3"),
            param_bytes(parameters, "D_VALUE_4"),
            param_bytes(parameters, "D_VALUE_5"),
            param_bytes(parameters, "D_VALUE_6"),
            param_bytes(parameters, "D_VALUE_7"),
        ]
        g_value_matrix = [
            param_bytes(parameters, "G_VALUE_0"),
            param_bytes(parameters, "G_VALUE_1"),
            param_bytes(parameters, "G_VALUE_2"),
            param_bytes(parameters, "G_VALUE_3"),
            param_bytes(parameters, "G_VALUE_4"),
            param_bytes(parameters, "G_VALUE_5"),
            param_bytes(parameters, "G_VALUE_6"),
            param_bytes(parameters, "G_VALUE_7"),
        ]

        if len(seed) != 4 or key_length != 4:
            return None

        working_seed = bytes([seed[3], seed[2], seed[1], seed[0]])

        d_bit2 = get_bit((working_seed[3] ^ working_seed[1]) & 0xFF, 1)
        d_bit1 = get_bit(working_seed[2], 4)
        d_bit0 = get_bit(working_seed[0], 6)
        d_value = self._create_d_value(d_bit2, d_bit1, d_bit0, d_value_matrix)

        seed_as_int = bytes_to_int(working_seed, LITTLE)

        d_xor_intermediate = (seed_as_int ^ d_value) & U32

        g_bit0 = get_bit(get_byte(d_xor_intermediate, 3), 4)
        g_bit1 = get_bit(working_seed[0], 1)
        g_bit2 = get_bit(working_seed[2], 6)

        g_value = self._create_d_value(g_bit2, g_bit1, g_bit0, g_value_matrix)

        seed_key = (d_xor_intermediate ^ g_value) & U32

        out_key = bytearray(4)
        out_key[0:4] = int_to_bytes(seed_key, BIG)
        return bytes(out_key)
