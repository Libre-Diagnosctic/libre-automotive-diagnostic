"""KIAlgo1 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/KIAlgo1.cs (MIT, (c) 2020 JinGen Lim).
Contribution by Vladyslav Lupashevskyi (@VladLupashevskyi):
https://github.com/jglim/UnlockECU/issues/12
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


def _bit_set(input_val: int, bit: int) -> bool:
    # C# BitSet: (input & (1 << bit)) > 0
    return (input_val & (1 << bit)) > 0


def _rotate_left_u16(input_val: int, rotations: int) -> int:
    # C# local RotateLeft on a ushort (16-bit rotate with carry from MSB)
    input_val &= 0xFFFF
    for _ in range(rotations):
        if (input_val & 0x8000) == 0:
            input_val = (input_val << 1) & 0xFFFF
        else:
            input_val = (input_val << 1) & 0xFFFF
            input_val |= 1
    return input_val & 0xFFFF


def _rotate_right_u32(input_val: int, rotations: int) -> int:
    # C# local RotateRight on a uint (32-bit rotate with carry into MSB)
    input_val &= U32
    for _ in range(rotations):
        if (input_val & 1) == 0:
            input_val >>= 1
        else:
            input_val >>= 1
            input_val |= 0x80000000
    return input_val & U32


class KIAlgo1(SecurityProvider):
    NAME = "KIAlgo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        level = param_byte(parameters, "Level")
        root_bytes = param_bytes(parameters, "K")
        root_rotated = bytes_to_int(root_bytes, BIG)

        if (len(seed) != 8) or (key_length != 7):
            return None

        seed_regrouped = bytes_to_int(
            bytes([seed[2], seed[6], seed[0], seed[4]]), LITTLE
        )
        rotation_count = (seed_regrouped & 7) + 2

        for _ in range(rotation_count):
            msb_set = (_bit_set(root_rotated, 0)
                       ^ _bit_set(root_rotated, 7)
                       ^ _bit_set(root_rotated, 17)
                       ^ _bit_set(root_rotated, 26))
            root_rotated &= 0x7FFFFFFF
            root_rotated |= 0x80000000 if msb_set else 0
            root_rotated = _rotate_right_u32(root_rotated, 1)

        seed_high = (seed_regrouped >> 16) & 0xFFFF
        seed_low = seed_regrouped & 0xFFFF

        for _ in range(2):
            seed_high ^= seed_low
            seed_high = _rotate_left_u16(seed_high, rotation_count)
            tangled = (seed_high + (root_rotated & 0xFFFF)) & 0xFFFF
            root_rotated >>= 16
            seed_high = seed_low
            seed_low = tangled

        prefix = (seed_low | (seed_high << 16)) & U32
        prefix_bytes = int_to_bytes(prefix, LITTLE)

        out_key = bytearray(key_length)
        out_key[1] = prefix_bytes[0]
        out_key[2] = prefix_bytes[1]
        out_key[3] = prefix_bytes[3]
        out_key[4] = prefix_bytes[2]

        # Originally documented as 'access level'
        out_key[0] = level

        # VCI fingerprint
        out_key[5] = 0xFF
        out_key[6] = 0xFF

        return bytes(out_key)
