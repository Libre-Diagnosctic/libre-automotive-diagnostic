"""OCM172 seed/key provider — ported from jglim/UnlockECU (OCM172.cs).

UnlockECU (https://github.com/jglim/UnlockECU, MIT, (c) 2020 JinGen Lim).
Passes the 2-byte input seed straight through as the output key.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import SecurityProvider, Parameter


class OCM172(SecurityProvider):
    NAME = "OCM172"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        if (len(seed) != 2) or (key_length != 2):
            return None

        out_key = bytearray(2)
        out_key[0] = seed[0]
        out_key[1] = seed[1]
        return bytes(out_key)
