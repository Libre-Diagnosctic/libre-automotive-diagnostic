"""RenaultRadio seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/RenaultRadio.cs

Computes a Renault radio unlock code from the first 4 seed bytes (interpreted
as ASCII, e.g. "Y020"). Produces a 4-digit decimal code packed as two BCD bytes.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter,
)


def _c_mod(a: int, b: int) -> int:
    """C# integer '%' — result takes the sign of the dividend (truncates toward zero)."""
    r = abs(a) % abs(b)
    return -r if a < 0 else r


class RenaultRadio(SecurityProvider):
    NAME = "RenaultRadio"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if seed is None:
            return None

        # Expecting 4 bytes (HEX: 59 30 32 30)
        if len(seed) < 4:
            return None

        # First 4 bytes as ASCII
        c0 = seed[0]
        c1 = seed[1]
        c2 = seed[2]
        c3 = seed[3]

        # char.ToUpper(c0): only affects ASCII lowercase letters.
        var0 = c0
        if ord('a') <= c0 <= ord('z'):
            var0 = c0 - 0x20
        var1 = c1
        var2 = c2
        var3 = c3

        var0 = var0 * 5
        var1 = var0 * 2 + var1 - 698
        var2 = (var2 * 5) * 2 + var1
        var3 = var3 + var2 - 528

        # C# int '%' truncates toward zero; Python '%' floors. Emulate C# %.
        sum_ = _c_mod((var3 << 3) - var3, 100)

        if sum_ < 0:
            sum_ += 100

        call = sum_ // 10
        remainder = _c_mod(sum_, 10) * 5  # sum_ >= 0 here, so equal to sum_ % 10

        varf = remainder * 2 + call

        if var1 == 0:
            return None

        eax = _c_mod(_c_mod(259, var1), 100)
        eax = eax * 5
        edx = eax * 5
        eax = edx * 4 + varf

        # OUTPUT (2 bytes Big Endian)
        out_key = bytearray(key_length)
        if len(out_key) < 2:
            return None

        s = f"{eax:04d}"  # C# eax.ToString("D4")

        out_key[0] = (((ord(s[0]) - ord('0')) << 4) | (ord(s[1]) - ord('0'))) & 0xFF
        out_key[1] = (((ord(s[2]) - ord('0')) << 4) | (ord(s[3]) - ord('0'))) & 0xFF

        return bytes(out_key)
