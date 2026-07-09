"""VDOSecurityAlgo seed/key provider — ported from jglim/UnlockECU (VDOSecurityAlgo.cs).

UnlockECU (https://github.com/jglim/UnlockECU, MIT, (c) 2020 JinGen Lim).

Very similar to Mattwmaster58's IC204, except this splits out the key
expansion level. Operates on an 8-byte seed with an 8-byte key constant "K"
and an integer "InternalLevel" parameter (the key expansion level).

All byte arithmetic is masked ``& 0xFF`` and all 32-bit sums ``& U32`` to match
C# ``byte``/``uint`` wraparound.
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import SecurityProvider, Parameter, U32


class VDOSecurityAlgo(SecurityProvider):
    NAME = "VDOSecurityAlgo"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        kc = bytearray(self.param_bytes(parameters, "K"))
        key_expansion_level = self.param_int(parameters, "InternalLevel")

        if (len(seed) != 8) or (key_length != 8):
            return None

        result = self._generate_key(key_expansion_level, seed, kc)

        out_key = bytearray(8)
        # Array.ConstrainedCopy(result, 0, outKey, 0, inSeed.Length) -> 8 bytes
        out_key[0:8] = result[0:8]
        return bytes(out_key)

    def _generate_key(
        self,
        key_expansion_level: int,
        seed: bytes,
        kc: bytearray,
        tpc_scrambler_level: int = -1,
    ) -> bytearray:
        if tpc_scrambler_level == -1:
            tpc_scrambler_level = key_expansion_level

        tp = bytearray([
            seed[7], seed[4], seed[3], seed[6],
            seed[5], seed[1], seed[0], seed[2],
        ])
        ik = self._expand_and_transform_key(key_expansion_level, tp, kc)  # sp[8-f]

        tpc = bytearray([tp[0], tp[1], tp[2], tp[3], tp[4], tp[5], tp[6], tp[7]])  # sp[0-7]

        for _cipher_iter in range(2):
            for i in range(4):
                tp[i] = (tp[i] ^ tp[4 + i]) & 0xFF

            rotate_count = tpc[tpc_scrambler_level] & 3
            rotate_count += 1

            lower_rotate_bytes = bytearray([tp[0], tp[1], tp[2], tp[3]])

            for _ in range(rotate_count):
                self._rotate_bits(lower_rotate_bytes)
            tp[0] = lower_rotate_bytes[0]
            tp[1] = lower_rotate_bytes[1]
            tp[2] = lower_rotate_bytes[2]
            tp[3] = lower_rotate_bytes[3]

            tp_sum = tp[0]
            tp_sum |= (tp[1] << 8)
            tp_sum |= (tp[2] << 16)
            tp_sum |= (tp[3] << 24)
            tp_sum &= U32

            ik_sum = ik[0]
            ik_sum |= (ik[1] << 8)
            ik_sum |= (ik[2] << 16)
            ik_sum |= (ik[3] << 24)
            ik_sum &= U32

            tp_sum = (tp_sum + ik_sum) & U32
            tp[0] = (tp_sum >> 0) & 0xFF
            tp[1] = (tp_sum >> 8) & 0xFF
            tp[2] = (tp_sum >> 16) & 0xFF
            tp[3] = (tp_sum >> 24) & 0xFF

            tp[4] = tpc[0]
            tp[5] = tpc[1]
            tp[6] = tpc[2]
            tp[7] = tpc[3]

            tpc[0:8] = tp[0:8]

            for i in range(4):
                tp[i] = (tp[i] ^ tp[4 + i]) & 0xFF

            rotate_count2 = tpc[tpc_scrambler_level] & 3
            rotate_count2 += 1

            lower_rotate_bytes2 = bytearray([tp[0], tp[1], tp[2], tp[3]])

            for _ in range(rotate_count2):
                self._rotate_bits(lower_rotate_bytes2)
            tp[0] = lower_rotate_bytes2[0]
            tp[1] = lower_rotate_bytes2[1]
            tp[2] = lower_rotate_bytes2[2]
            tp[3] = lower_rotate_bytes2[3]

            tp_sum2 = tp[0]
            tp_sum2 |= (tp[1] << 8)
            tp_sum2 |= (tp[2] << 16)
            tp_sum2 |= (tp[3] << 24)
            tp_sum2 &= U32

            ik_sum2 = ik[4]
            ik_sum2 |= (ik[5] << 8)
            ik_sum2 |= (ik[6] << 16)
            ik_sum2 |= (ik[7] << 24)
            ik_sum2 &= U32

            tp_sum2 = (tp_sum2 + ik_sum2) & U32
            tp[0] = (tp_sum2 >> 0) & 0xFF
            tp[1] = (tp_sum2 >> 8) & 0xFF
            tp[2] = (tp_sum2 >> 16) & 0xFF
            tp[3] = (tp_sum2 >> 24) & 0xFF

            tp[4] = tpc[0]
            tp[5] = tpc[1]
            tp[6] = tpc[2]
            tp[7] = tpc[3]

            tpc[0:8] = tp[0:8]

        key = bytearray([
            tpc[3], tpc[5], tpc[6], tpc[1],
            tpc[0], tpc[7], tpc[4], tpc[2],
        ])
        return key

    def _expand_and_transform_key(
        self,
        access_level: int,
        transposed_seed: bytearray,
        kc: bytearray,
    ) -> bytearray:
        morph_count = (transposed_seed[access_level] & 7) + 2
        self._expand_full_key(kc)

        m_key = bytearray([0, 0, 0, 0, 0, 0, 0, 0])
        m_key[0:8] = kc[0:8]

        for _ in range(morph_count):
            ek = bytearray([
                m_key[0], m_key[1], m_key[2], m_key[3],
                m_key[4], m_key[5], m_key[6], m_key[7],
            ])

            xor_intermediate = 0

            ek[0] &= 8
            ek[0] >>= 3
            xor_intermediate ^= ek[0]

            ek[1] &= 1
            ek[1] >>= 0
            xor_intermediate ^= ek[1]

            ek[2] &= 2
            ek[2] >>= 1
            xor_intermediate ^= ek[2]

            ek[3] &= 0x80
            ek[3] >>= 7
            xor_intermediate ^= ek[3]

            ek[4] &= 0x20
            ek[4] >>= 5
            xor_intermediate ^= ek[4]

            ek[5] &= 4
            ek[5] >>= 2
            xor_intermediate ^= ek[5]

            ek[6] &= 0x40
            ek[6] >>= 6
            xor_intermediate ^= ek[6]

            snapshot = ek[7]
            ek[7] &= 0x10
            ek[7] >>= 4
            xor_intermediate ^= ek[7]

            final_byte_transformed = (xor_intermediate << 7) & 0xFF
            final_byte_transformed |= (snapshot & 0x7F)

            m_key[7] = final_byte_transformed & 0xFF
            self._rotate_bits(m_key)

        return m_key

    def _expand_full_key(self, key_constant: bytearray) -> None:
        key_lower = bytearray([key_constant[0], key_constant[1], key_constant[2], key_constant[3]])
        key_upper = bytearray([key_constant[4], key_constant[5], key_constant[6], key_constant[7]])
        self._expand_32bit_key(key_lower)
        self._expand_32bit_key(key_upper)
        key_constant[0:4] = key_lower[0:4]
        key_constant[4:8] = key_upper[0:4]

    def _expand_32bit_key(self, key: bytearray) -> None:
        key_a = bytearray([key[0], key[1], key[2], key[3]])
        key_p = bytearray([key[1], key[3], key[0], key[2]])

        rotate_count_p = (key[2] & 0xF) + 1
        self._rotate_bits_n(key_p, rotate_count_p)

        rotate_count_a = (key[3] & 0xF) + 1
        self._rotate_bits_n(key_a, rotate_count_a)

        for i in range(len(key)):
            key[i] = (key_a[i] ^ key_p[i]) & 0xFF

    def _rotate_bits_n(self, in_bytes: bytearray, count: int) -> None:
        for _ in range(count):
            self._rotate_bits(in_bytes)

    def _rotate_bits(self, in_bytes: bytearray) -> None:
        temp_buffer = bytearray(len(in_bytes))
        for i in range(len(temp_buffer)):
            if (in_bytes[i] & 1) > 0:
                temp_buffer[i] = 0x80
        for i in range(len(temp_buffer)):
            r_index = i - 1
            if r_index < 0:
                r_index = len(temp_buffer) - 1
            in_bytes[i] = (in_bytes[i] >> 1) & 0xFF
            in_bytes[i] = (in_bytes[i] | temp_buffer[r_index]) & 0xFF
