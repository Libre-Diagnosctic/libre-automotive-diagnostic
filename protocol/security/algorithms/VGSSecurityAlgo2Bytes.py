"""VGSSecurityAlgo2Bytes seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/VGSSecurityAlgo2Bytes.cs (MIT, (c) 2020 JinGen Lim).
Implementation of VGSSecurityAlgo for 2-byte seed/key pairs.
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


class VGSSecurityAlgo2Bytes(SecurityProvider):
    NAME = "VGSSecurityAlgo2Bytes"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        crypto_key_bytes = param_bytes(parameters, "K")
        crypto_key = (crypto_key_bytes[1] | ((crypto_key_bytes[0] & U32) << 8)) & U32

        if len(seed) != 2 or key_length != 2:
            return None

        seed_val = (seed[0] | ((seed[1] & U32) << 8)) & U32
        seed_key = (crypto_key * ((crypto_key ^ seed_val) & U32)) & U32

        out_key = bytearray(2)
        out_key[0] = (seed_key >> 8) & 0xFF
        out_key[1] = seed_key & 0xFF
        return bytes(out_key)
