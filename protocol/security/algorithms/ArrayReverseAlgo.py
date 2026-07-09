"""ArrayReverseAlgo seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/ArrayReverseAlgo.cs

Generic array reverse algorithm: seed and output are the same length and the
output is the reversed seed array.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter,
)


class ArrayReverseAlgo(SecurityProvider):
    NAME = "ArrayReverseAlgo"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if len(seed) != key_length:
            return None

        # C# reverses inSeed in place then copies into outKey.
        out_key = bytearray(seed)
        out_key.reverse()
        return bytes(out_key)
