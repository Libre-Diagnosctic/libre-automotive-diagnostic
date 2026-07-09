"""ORC166 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/ORC166.cs

Contribution by Florian Pradines @Flo354 (UnlockECU issue #18).
[!] Not verified against a known seed/key pair. Derives four permuted bytes
from the first 4 seed bytes, packs them big-endian, and adds a static key.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter, BIG, U32,
    param_bytes, bytes_to_int, int_to_bytes,
)


class ORC166(SecurityProvider):
    NAME = "ORC166"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        crypto_key_bytes = param_bytes(parameters, "staticKey")
        crypto_key = bytes_to_int(crypto_key_bytes, BIG)

        if key_length != 4:
            return None
        # Seed can be either 4 or 8 bytes. Only first 4 bytes are used.
        if not ((len(seed) == 4) or (len(seed) == 8)):
            return None

        # C# 'long' math; byte shifts promoted to int. No masking until final cast.
        i0 = (seed[0] >> 1) + (seed[1] << 1) + (seed[2] >> 2) + (seed[3] << 2)
        i1 = (seed[0] << 1) + (seed[1] >> 1) + (seed[2] << 2) + (seed[3] >> 2)
        i2 = (seed[0] >> 2) + (seed[1] << 2) + (seed[2] >> 1) + (seed[3] << 1)
        i3 = (seed[0] << 2) + (seed[1] >> 2) + (seed[2] << 1) + (seed[3] >> 1)

        i0 = (i0 & 0xFF) << 24
        i1 = (i1 & 0xFF) << 16
        i2 = (i2 & 0xFF) << 8
        i3 = (i3 & 0xFF) << 0

        seed_key = crypto_key + i0 + i1 + i2 + i3

        out_key = bytearray(key_length)
        out_key[0:4] = int_to_bytes(seed_key & U32, BIG)
        return bytes(out_key)
