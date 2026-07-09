"""VGSSecurityAlgoExt seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/VGSSecurityAlgoExt.cs (MIT, (c) 2020 JinGen Lim).
Extended VGS Algo with different keys for multiplication and xor.
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


class VGSSecurityAlgoExt(SecurityProvider):
    NAME = "VGSSecurityAlgoExt"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        crypto_key_mult_bytes = param_bytes(parameters, "M")
        crypto_key_mult = bytes_to_int(crypto_key_mult_bytes, BIG)

        crypto_key_xor_bytes = param_bytes(parameters, "X")
        crypto_key_xor = bytes_to_int(crypto_key_xor_bytes, BIG)

        if len(seed) != 4 or key_length != 4:
            return None

        # C# 'long' math: cryptoKeyMult (uint) * (cryptoKeyXor ^ seed).
        seed_val = bytes_to_int(seed, BIG)
        seed_key = crypto_key_mult * (crypto_key_xor ^ seed_val)

        out_key = bytearray(4)
        out_key[:] = int_to_bytes(seed_key & U32, BIG)
        return bytes(out_key)
