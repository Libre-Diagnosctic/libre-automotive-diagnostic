"""EsLibEd25519 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/EsLibEd25519.cs

Used for modern ECUs. The C# uses BouncyCastle's ``Ed25519phSigner`` with an
empty context: this is RFC 8032 Ed25519ph (the pre-hash variant). The 32-byte
seed is the "message", which is pre-hashed with SHA-512, and signing uses the
``dom2(phflag=1, context="")`` domain-separation prefix. The 64-byte signature
is returned as the key.

``Ed25519PrivateKeyParameters(privateKeyBytes, 0)`` interprets the parameter as
a 32-byte Ed25519 *seed* (not the expanded secret scalar); the reference
key-expansion (SHA-512 of the seed, clamp, prefix) is performed below.

We implement the RFC 8032 reference math directly because Python's stdlib and
``cryptography`` only expose plain Ed25519 (PureEdDSA), not the ph variant.

Parameters (from db.json):
  "PrivateKey" (ByteArray, 32 bytes): Ed25519 seed
"""
from __future__ import annotations

import hashlib
from typing import List, Optional, Tuple

from ..provider import (
    SecurityProvider, Parameter,
    param_bytes,
)

# --------------------------------------------------------------------------- #
#  RFC 8032 Ed25519 reference implementation (edwards25519)
# --------------------------------------------------------------------------- #
_b = 256
_q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493  # group order

# d = -121665/121666 (mod q)
_d = (-121665 * pow(121666, _q - 2, _q)) % _q
# I = sqrt(-1) (mod q)
_I = pow(2, (_q - 1) // 4, _q)


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_int(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little")


def _inv(x: int) -> int:
    return pow(x, _q - 2, _q)


def _x_recover(y: int) -> int:
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = (4 * _inv(5)) % _q
_Bx = _x_recover(_By)
# Base point in extended-affine (x, y, z, t) coordinates.
_B = (_Bx % _q, _By % _q, 1, (_Bx * _By) % _q)


def _edwards_add(P: Tuple[int, int, int, int],
                 Q: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    # Extended twisted Edwards addition (a = -1).
    (x1, y1, z1, t1) = P
    (x2, y2, z2, t2) = Q
    a = ((y1 - x1) * (y2 - x2)) % _q
    b = ((y1 + x1) * (y2 + x2)) % _q
    c = (t1 * 2 * _d * t2) % _q
    dd = (z1 * 2 * z2) % _q
    e = b - a
    f = dd - c
    g = dd + c
    h = b + a
    x3 = (e * f) % _q
    y3 = (g * h) % _q
    t3 = (e * h) % _q
    z3 = (f * g) % _q
    return (x3, y3, z3, t3)


def _scalarmult(P: Tuple[int, int, int, int], e: int) -> Tuple[int, int, int, int]:
    if e == 0:
        return (0, 1, 1, 0)
    Q = _scalarmult(P, e // 2)
    Q = _edwards_add(Q, Q)
    if e & 1:
        Q = _edwards_add(Q, P)
    return Q


def _encode_point(P: Tuple[int, int, int, int]) -> bytes:
    (x, y, z, t) = P
    zi = _inv(z)
    x = (x * zi) % _q
    y = (y * zi) % _q
    # y with the low bit set to x's parity in the top bit.
    val = y | ((x & 1) << 255)
    return val.to_bytes(32, "little")


def _ed25519_sign_prehash(prehashed_message: bytes, seed: bytes) -> bytes:
    """RFC 8032 Ed25519ph signing with an empty context.

    ``prehashed_message`` is SHA-512(message); ``seed`` is the 32-byte secret.
    """
    # Key expansion.
    h = _sha512(seed)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8   # clear low 3 bits
    a |= (1 << 254)       # set bit 254
    prefix = h[32:64]

    # Public key A = [a]B.
    A = _encode_point(_scalarmult(_B, a))

    # dom2(x=1, y="") = "SigEd25519 no Ed25519 collisions" || phflag || ctxlen || ctx
    dom2 = b"SigEd25519 no Ed25519 collisions" + bytes([1]) + bytes([0])

    # r = SHA-512(dom2 || prefix || PH(M)) mod L
    r = _sha512_int(dom2 + prefix + prehashed_message) % _L
    R = _encode_point(_scalarmult(_B, r))

    # k = SHA-512(dom2 || R || A || PH(M)) mod L
    k = _sha512_int(dom2 + R + A + prehashed_message) % _L
    s = (r + k * a) % _L

    return R + s.to_bytes(32, "little")


class EsLibEd25519(SecurityProvider):
    NAME = "EsLibEd25519"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        privateKeyBytes = param_bytes(parameters, "PrivateKey")

        if (len(seed) != 32) or (key_length != 64):
            return None

        # Ed25519ph: pre-hash the seed (the "message") with SHA-512, then sign
        # with an empty context. Signature is 64 bytes -> the output key.
        prehash = _sha512(seed)
        signature = _ed25519_sign_prehash(prehash, privateKeyBytes)

        out_key = bytearray(64)
        out_key[0:len(signature)] = signature
        return bytes(out_key)
