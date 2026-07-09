"""DRVU_PROF seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/DRVU_PROF.cs

Simpler version of DaimlerStandardSecurityAlgo with custom kA, kC, and no blockB.
Computes  key = ((kA * seedA + kC) mod cryptoKey), truncated to 32 bits.

Parameters (from db.json):
  "KeyConst" (ByteArray, 4 bytes): 32-bit crypto key (big-endian modulus)
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter, U32, BIG,
    param_bytes, bytes_to_int, int_to_bytes,
)


class DRVU_PROF(SecurityProvider):
    NAME = "DRVU_PROF"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        cryptoKeyBytes = param_bytes(parameters, "KeyConst")
        cryptoKey = bytes_to_int(cryptoKeyBytes, BIG)

        # C# long constants (64-bit signed).
        kA = 258028488
        kC = 1583629211

        if (len(seed) != 4) or (key_length != 4):
            return None

        seedA = bytes_to_int(seed, BIG, 0)

        # long arithmetic — fits in 64 bits, no masking needed until the cast.
        intermediate1 = kA * seedA + kC
        seedKey = intermediate1 % cryptoKey

        out_key = bytearray(int_to_bytes(seedKey & U32, BIG))  # (uint)seedKey
        return bytes(out_key)
