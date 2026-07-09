"""XorAlgo seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/XorAlgo.cs

Generic XOR algorithm: seed, xor key, and output are all the same length and
``output = seed ^ xorKey``.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter,
    param_bytes,
)


class XorAlgo(SecurityProvider):
    NAME = "XorAlgo"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        xor_key = param_bytes(parameters, "K")

        if (len(seed) != key_length) or (len(seed) != len(xor_key)):
            return None

        out_key = bytearray(key_length)
        for i in range(len(seed)):
            out_key[i] = (seed[i] ^ xor_key[i]) & 0xFF
        return bytes(out_key)
