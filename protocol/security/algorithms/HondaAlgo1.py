"""HondaAlgo1 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/HondaAlgo1.cs

Level 1 provider used for firmware flashing. Keys are embedded as a 12-byte
ASCII block in the *.rwd.gz firmware files. Uses three 16-bit parameters
(xor / mul / mod) packed into the "K" ByteArray.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter,
    param_bytes,
)


class HondaAlgo1(SecurityProvider):
    NAME = "HondaAlgo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 2) or (key_length != 2):
            return None

        k = param_bytes(parameters, "K")

        k0_xor = (k[0] << 8 | k[1]) & 0xFFFF
        k1_mul = (k[2] << 8 | k[3]) & 0xFFFF
        k2_mod = (k[4] << 8 | k[5]) & 0xFFFF
        seed_u = (seed[0] << 8 | seed[1]) & 0xFFFF

        key = seed_u * k1_mul
        if k2_mod != 0:
            key %= k2_mod
        key ^= (k0_xor + seed_u)
        key &= 0xFFFF

        out_key = bytearray(2)
        out_key[0] = (key >> 8) & 0xFF
        out_key[1] = key & 0xFF
        return bytes(out_key)
