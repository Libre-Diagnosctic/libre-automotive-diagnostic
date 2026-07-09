"""RDU222 seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/RDU222.cs (MIT, (c) 2020 JinGen Lim).
seed |= A, ^= B, += C.
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


class RDU222(SecurityProvider):
    NAME = "RDU222"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        # BytesToInt returns uint; assigned to C# 'long' (non-negative, fits).
        param_a = bytes_to_int(param_bytes(parameters, "a"), BIG)
        param_b = bytes_to_int(param_bytes(parameters, "b"), BIG)
        param_c = bytes_to_int(param_bytes(parameters, "c"), BIG)

        if len(seed) != 4 or key_length != 4:
            return None

        # C# 'long' math — unbounded in Python, masked at the (uint) output cast.
        in_seed_as_long = bytes_to_int(seed, BIG)

        in_seed_as_long |= param_a
        in_seed_as_long ^= param_b
        in_seed_as_long += param_c

        out_key = bytearray(4)
        out_key[:] = int_to_bytes(in_seed_as_long & U32, BIG)
        return bytes(out_key)
