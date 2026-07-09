"""RBTM seed/key provider — ported from jglim/UnlockECU (RBTM.cs).

UnlockECU (https://github.com/jglim/UnlockECU, MIT, (c) 2020 JinGen Lim).
Passes the 4-byte input seed straight through as the output key.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import SecurityProvider, Parameter


class RBTM(SecurityProvider):
    NAME = "RBTM"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        if (len(seed) != 4) or (key_length != 4):
            return None

        out_key = bytearray(4)
        out_key[0] = seed[0]
        out_key[1] = seed[1]
        out_key[2] = seed[2]
        out_key[3] = seed[3]
        return bytes(out_key)
