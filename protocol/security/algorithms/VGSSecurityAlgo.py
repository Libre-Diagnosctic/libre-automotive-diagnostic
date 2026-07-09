"""VGSSecurityAlgo seed/key provider — ported from jglim/UnlockECU.

Source: UnlockECU/Security/VGSSecurityAlgo.cs (MIT, (c) 2020 JinGen Lim).
Implementation of VGS Algo from VGSNAG2. The name is unofficial.
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


class VGSSecurityAlgo(SecurityProvider):
    NAME = "VGSSecurityAlgo"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        crypto_key_bytes = param_bytes(parameters, "K")
        crypto_key = bytes_to_int(crypto_key_bytes, BIG)

        if len(seed) != 4 or key_length != 4:
            return None

        # C# 'long' math: cryptoKey (uint) * (cryptoKey ^ seed). Both operands
        # are non-negative and fit in long; masked to uint at the output cast.
        seed_val = bytes_to_int(seed, BIG)
        seed_key = crypto_key * (crypto_key ^ seed_val)

        out_key = bytearray(4)
        out_key[:] = int_to_bytes(seed_key & U32, BIG)
        return bytes(out_key)
