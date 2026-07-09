"""SubaruSecurityAccess2018CY1 provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/SubaruSecurityAccess2018CY1.cs

Subaru SecurityAccess2018CY1 from SSM4. The 16-byte seed is encrypted through
AES-128 using a variant-specific key ("K") and a 16-byte zero IV. The C# uses
BouncyCastle CbcBlockCipher(AesEngine) processing exactly one block; for a
single block with a zero IV this is identical to AES-128-ECB (no padding).
Led/confirmed by @jnewb1 (UnlockECU issue #25).
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter,
    param_bytes,
)

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class SubaruSecurityAccess2018CY1(SecurityProvider):
    NAME = "SubaruSecurityAccess2018CY1"

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        if (len(seed) != 16) or (key_length != 16):
            return None

        k = param_bytes(parameters, "K")

        # CbcBlockCipher(AesEngine) with a 16-byte zero IV, one block, no padding.
        # For a single block with a zero IV, CBC == ECB.
        cipher = Cipher(algorithms.AES(bytes(k)), modes.CBC(b"\x00" * 16))
        enc = cipher.encryptor()
        out = enc.update(bytes(seed[0:16])) + enc.finalize()

        out_key = bytearray(16)
        out_key[0:16] = out[0:16]
        return bytes(out_key)
