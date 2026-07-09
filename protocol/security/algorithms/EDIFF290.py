"""EDIFF290 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/EDIFF290.cs

Simpler version of DaimlerStandardSecurityAlgo with custom kA, kC, and no blockB.
Similar to DRVU_PROF but with different initial parameter data types: kA and kC
are Int32 parameters, and the multiply/add are each masked to 32 bits.

  key = ((((kA * seedA) & 0xFFFFFFFF) + kC) & 0xFFFFFFFF) mod cryptoKey

Parameters (from db.json):
  "KeyK" (ByteArray, 4 bytes): 32-bit crypto key (big-endian modulus)
  "kA"   (Int32): multiplier
  "kC"   (Int32): addend
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter, U32, BIG,
    param_bytes, param_int, bytes_to_int, int_to_bytes,
)


class EDIFF290(SecurityProvider):
    NAME = "EDIFF290"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        cryptoKeyBytes = param_bytes(parameters, "KeyK")
        cryptoKey = bytes_to_int(cryptoKeyBytes, BIG)

        # GetParameterInteger returns a signed Int32, widened to C# long.
        kA = param_int(parameters, "kA")
        kC = param_int(parameters, "kC")

        # inSeed is 8 bytes but only the first 4 are consumed by BytesToInt.
        if (len(seed) != 8) or (key_length != 4):
            return None

        seedA = bytes_to_int(seed, BIG, 0)

        # kA * seedA + kC, but constrained to 32 bits at each step (long math).
        intermediate1 = kA * seedA
        intermediate1 &= 0xFFFFFFFF
        intermediate1 += kC
        intermediate1 &= 0xFFFFFFFF

        seedKey = intermediate1 % cryptoKey

        out_key = bytearray(int_to_bytes(seedKey & U32, BIG))  # (uint)seedKey
        return bytes(out_key)
