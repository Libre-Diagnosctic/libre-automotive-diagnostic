"""PowertrainSecurityAlgo — ported from jglim/UnlockECU.

Faithful Python port of ``Security/PowertrainSecurityAlgo.cs`` from UnlockECU
(https://github.com/jglim/UnlockECU, MIT, (c) 2020 JinGen Lim).

Basic matrix/bit-selected XOR seed/key algorithm used by CRD-series ECUs.
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


class PowertrainSecurityAlgo(SecurityProvider):
    NAME = "PowertrainSecurityAlgo"

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
        i = set_byte(i, matrix[j][2], 0)
        i = set_byte(i, matrix[j][1], 1)
        i = set_byte(i, matrix[j][0], 2)
        i = set_byte(i, matrix[j][3], 3)
        return i & U32

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        matrix = [
            [param_byte(parameters, "X00"), param_byte(parameters, "X01"), param_byte(parameters, "X02"), param_byte(parameters, "X03")],
            [param_byte(parameters, "X10"), param_byte(parameters, "X11"), param_byte(parameters, "X12"), param_byte(parameters, "X13")],
            [param_byte(parameters, "X20"), param_byte(parameters, "X21"), param_byte(parameters, "X22"), param_byte(parameters, "X23")],
            [param_byte(parameters, "X30"), param_byte(parameters, "X31"), param_byte(parameters, "X32"), param_byte(parameters, "X33")],
            [param_byte(parameters, "X40"), param_byte(parameters, "X41"), param_byte(parameters, "X42"), param_byte(parameters, "X43")],
            [param_byte(parameters, "X50"), param_byte(parameters, "X51"), param_byte(parameters, "X52"), param_byte(parameters, "X53")],
            [param_byte(parameters, "X60"), param_byte(parameters, "X61"), param_byte(parameters, "X62"), param_byte(parameters, "X63")],
            [param_byte(parameters, "X70"), param_byte(parameters, "X71"), param_byte(parameters, "X72"), param_byte(parameters, "X73")],
        ]

        i = [
            param_int(parameters, "i1"),
            param_int(parameters, "i2"),
            param_int(parameters, "i3"),
            param_int(parameters, "i4"),
            param_int(parameters, "i5"),
            param_int(parameters, "i6"),
        ]
        j = [
            param_int(parameters, "j1"),
            param_int(parameters, "j2"),
            param_int(parameters, "j3"),
            param_int(parameters, "j4"),
            param_int(parameters, "j5"),
            param_int(parameters, "j6"),
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
