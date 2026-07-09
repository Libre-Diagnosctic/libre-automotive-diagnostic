"""NetaAlgo1 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/NetaAlgo1.cs

Contribution by Ivan Beck @Ivanbk (UnlockECU issue #50). A CRC-16-style bit
mill seeded from a 2-byte "Pin" parameter, clocked by the two seed bytes.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter,
    param_bytes,
)


class NetaAlgo1(SecurityProvider):
    NAME = "NetaAlgo1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if key_length != 2:
            return None
        if len(seed) != 2:
            return None

        pin_bytes = param_bytes(parameters, "Pin")
        # C# 'long v', unbounded until masked below.
        v = pin_bytes[1] | (pin_bytes[0] << 8)

        for challenge_byte in seed:
            v ^= (challenge_byte << 8)
            for _ in range(8):
                if (v & 0x8000) == 0:
                    v = (v << 1) & 0xFFFF
                elif (v & 0x80) == 0:
                    v = ((v << 1) ^ 0x8025) & 0xFFFF
                else:
                    v = ((v << 1) ^ 0x8408) & 0xFFFF

        out_key = bytearray(2)
        out_key[0] = (v >> 8) & 0xFF
        out_key[1] = v & 0xFF
        return bytes(out_key)
