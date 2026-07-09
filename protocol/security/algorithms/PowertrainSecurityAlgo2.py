"""PowertrainSecurityAlgo2 — ported from jglim/UnlockECU.

Faithful Python port of ``Security/PowertrainSecurityAlgo2.cs`` from UnlockECU
(https://github.com/jglim/UnlockECU, MIT, (c) 2020 JinGen Lim).

Derivative of PowertrainSecurityAlgo with a slightly different byte ordering
when computing the g-value.
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


class PowertrainSecurityAlgo2(SecurityProvider):
    NAME = "PowertrainSecurityAlgo2"

    @staticmethod
    def _create_d_value(bit2_enabled: int, bit1_enabled: int, bit0_enabled: int,
                        matrix: List[List[int]]) -> int:
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

    @staticmethod
    def _create_g_value(bit2_enabled: int, bit1_enabled: int, bit0_enabled: int,
                        matrix: List[List[int]]) -> int:
        i = 0
        j = 0
        if bit0_enabled != 0:
            j = set_bit(j, 0)
        if bit1_enabled != 0:
            j = set_bit(j, 1)
        if bit2_enabled != 0:
            j = set_bit(j, 2)
        # Note: g-value byte ordering differs from PowertrainSecurityAlgo.
        i = set_byte(i, matrix[j][0], 0)
        i = set_byte(i, matrix[j][3], 1)
        i = set_byte(i, matrix[j][2], 2)
        i = set_byte(i, matrix[j][1], 3)
        return i & U32

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        matrix = [
            [param_byte(parameters, "XX00"), param_byte(parameters, "XX01"), param_byte(parameters, "XX02"), param_byte(parameters, "XX03")],
            [param_byte(parameters, "XX10"), param_byte(parameters, "XX11"), param_byte(parameters, "XX12"), param_byte(parameters, "XX13")],
            [param_byte(parameters, "XX20"), param_byte(parameters, "XX21"), param_byte(parameters, "XX22"), param_byte(parameters, "XX23")],
            [param_byte(parameters, "XX30"), param_byte(parameters, "XX31"), param_byte(parameters, "XX32"), param_byte(parameters, "XX33")],
            [param_byte(parameters, "XX40"), param_byte(parameters, "XX41"), param_byte(parameters, "XX42"), param_byte(parameters, "XX43")],
            [param_byte(parameters, "XX50"), param_byte(parameters, "XX51"), param_byte(parameters, "XX52"), param_byte(parameters, "XX53")],
            [param_byte(parameters, "XX60"), param_byte(parameters, "XX61"), param_byte(parameters, "XX62"), param_byte(parameters, "XX63")],
            [param_byte(parameters, "XX70"), param_byte(parameters, "XX71"), param_byte(parameters, "XX72"), param_byte(parameters, "XX73")],
        ]

        i = [
            param_int(parameters, "ii1"),
            param_int(parameters, "ii2"),
            param_int(parameters, "ii3"),
            param_int(parameters, "ii4"),
            param_int(parameters, "ii5"),
            param_int(parameters, "ii6"),
        ]
        j = [
            param_int(parameters, "jj1"),
            param_int(parameters, "jj2"),
            param_int(parameters, "jj3"),
            param_int(parameters, "jj4"),
            param_int(parameters, "jj5"),
            param_int(parameters, "jj6"),
        ]

        if len(seed) != 4 or key_length != 4:
            return None

        working_seed = bytes([seed[3], seed[2], seed[1], seed[0]])

        y = (working_seed[i[0]] ^ working_seed[i[1]]) & 0xFF
        d_bit2 = get_bit(working_seed[i[2]], j[0])
        d_bit1 = get_bit(working_seed[i[3]], j[1])
        d_bit0 = get_bit(y, j[2])
        d_value = self._create_d_value(d_bit2, d_bit1, d_bit0, matrix)

        seed_as_int = bytes_to_int(working_seed, LITTLE)

        d_xor_intermediate = (seed_as_int ^ d_value) & U32
        g_bit2 = get_bit(working_seed[i[4]], j[3])
        g_bit1 = get_bit(y, j[4])
        g_bit0 = get_bit(get_byte(d_xor_intermediate, i[5]), j[5])
        g_value = self._create_g_value(g_bit2, g_bit1, g_bit0, matrix)

        seed_key = (d_xor_intermediate ^ g_value) & U32

        out_key = bytearray(int_to_bytes(seed_key, BIG))
        return bytes(out_key)
