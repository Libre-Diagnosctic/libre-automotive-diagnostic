"""IC204 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/IC204.cs

IC204 Seed-Key Algorithm for Mercedes W204 instrument cluster (NEC V850E1).
Overview: permute seed -> derive LFSR iteration count -> generate 8-byte LFSR
state from the salt -> run LFSR -> Feistel-like network (2 rounds) -> reverse
permute to produce the 8-byte key.

Parameters (from db.json):
  "Salt" (ByteArray, 8 bytes): per-level salt table entry
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter, U32,
    param_bytes,
)


class IC204(SecurityProvider):
    NAME = "IC204"

    # UDS SecurityAccess sub-function to internal level mapping.
    @staticmethod
    def _uds_to_internal_level(uds_level: int) -> int:
        if uds_level == 0x01:
            return 1
        if uds_level == 0x03:
            return 3
        if uds_level == 0x09:
            return 5
        if uds_level == 0x0D:
            return 7
        return (uds_level + 1) // 2

    @staticmethod
    def _rotate_right_array(buf: bytearray, offset: int, length: int) -> None:
        """Right-rotate a byte array (contiguous bitfield) by 1 bit."""
        if length == 0 or length > 8:
            return

        carries = [0] * length
        for i in range(length):
            carries[i] = buf[offset + i] & 1

        for i in range(length):
            carry_idx = (length - 1) if i == 0 else (i - 1)
            shifted = (buf[offset + i] >> 1) & 0x7F
            if carries[carry_idx] != 0:
                shifted |= 0x80
            buf[offset + i] = shifted & 0xFF

    @staticmethod
    def _salt_transform(salt: bytes, output: bytearray) -> None:
        """FUN_00180bd2: generate 8-byte LFSR initial state from salt only."""
        local = bytearray(0x14)

        # Store salt at local[0x0C..0x13]
        local[0x0C:0x0C + 8] = salt[0:8]

        # Phase 1: salt[4..7] -> local[0x00..0x03]
        for i in range(4):
            local[i] = local[0x10 + i]

        # Phase 2: salt[0..3] -> local[0x04..0x07]
        for i in range(4):
            local[0x04 + i] = local[0x0C + i]

        # Phase 3: local[0x00..0x03] -> local[0x08..0x0B]
        for i in range(4):
            local[0x08 + i] = local[i]

        # Phase 4: Transpose local[0x08..0x0B] -> local[0x00..0x03]
        t0, t1, t2, t3 = local[0x08], local[0x09], local[0x0A], local[0x0B]
        local[0x02] = t0
        local[0x00] = t1
        local[0x01] = t3
        local[0x03] = t2

        # Phase 5: Rotate local[0x00..0x03] right by (t2 & 0xF) + 1
        rotate_count = (t2 & 0x0F) + 1
        for _ in range(rotate_count):
            IC204._rotate_right_array(local, 0, 4)

        # Phase 6: Rotate local[0x08..0x0B] right by (local[0x0B] & 0xF) + 1
        rotate_count = (local[0x0B] & 0x0F) + 1
        for _ in range(rotate_count):
            IC204._rotate_right_array(local, 0x08, 4)

        # Phase 7: XOR local[0..3] ^= local[0x08..0x0B]
        for i in range(4):
            local[i] ^= local[0x08 + i]

        # Phase 8: local[0x04..0x07] -> local[0x08..0x0B]
        for i in range(4):
            local[0x08 + i] = local[0x04 + i]

        # Phase 9: Transpose local[0x08..0x0B] -> local[0x04..0x07]
        t0, t1, t2, t3 = local[0x08], local[0x09], local[0x0A], local[0x0B]
        local[0x06] = t0
        local[0x04] = t1
        local[0x05] = t3
        local[0x07] = t2

        # Phase 10: Rotate local[0x04..0x07] right by (local[0x0A] & 0xF) + 1
        rotate_count = (local[0x0A] & 0x0F) + 1
        for _ in range(rotate_count):
            IC204._rotate_right_array(local, 0x04, 4)

        # Phase 11: Rotate local[0x08..0x0B] right by (local[0x0B] & 0xF) + 1
        rotate_count = (local[0x0B] & 0x0F) + 1
        for _ in range(rotate_count):
            IC204._rotate_right_array(local, 0x08, 4)

        # Phase 12: XOR local[0x04..0x07] ^= local[0x08..0x0B]
        for i in range(4):
            local[0x04 + i] ^= local[0x08 + i]

        # Phase 13: local[0x00..0x03] -> local[0x10..0x13]
        for i in range(4):
            local[0x10 + i] = local[i]

        # Phase 14: local[0x04..0x07] -> local[0x0C..0x0F]
        for i in range(4):
            local[0x0C + i] = local[0x04 + i]

        # Output: local[0x0C..0x13] (8 bytes)
        output[0:8] = local[0x0C:0x0C + 8]

    @staticmethod
    def _compute_lfsr_feedback(ws: bytearray) -> None:
        """LFSR feedback: XOR 8 specific bit taps, write into bit 7 of ws[0x0F]."""
        fb = (ws[0x08] >> 3) & 1
        fb ^= ws[0x09] & 1
        fb ^= (ws[0x0A] >> 1) & 1
        fb ^= (ws[0x0B] >> 7) & 1
        fb ^= (ws[0x0C] >> 5) & 1
        fb ^= (ws[0x0D] >> 2) & 1
        fb ^= (ws[0x0E] >> 6) & 1
        fb ^= (ws[0x0F] >> 4) & 1
        ws[0x0F] = ((ws[0x0F] & 0x7F) | (fb << 7)) & 0xFF

    @staticmethod
    def _le32_load(buf: bytearray, offset: int) -> int:
        return (
            ((buf[offset + 3] << 24)
             | (buf[offset + 2] << 16)
             | (buf[offset + 1] << 8)
             | buf[offset]) & U32
        )

    @staticmethod
    def _le32_store(buf: bytearray, offset: int, val: int) -> None:
        buf[offset] = val & 0xFF
        buf[offset + 1] = (val >> 8) & 0xFF
        buf[offset + 2] = (val >> 16) & 0xFF
        buf[offset + 3] = (val >> 24) & 0xFF

    def generate_key(self, seed: bytes, key_length: int,
                     access_level: int, parameters: List[Parameter]) -> Optional[bytes]:
        salt = param_bytes(parameters, "Salt")

        if len(seed) != 8 or key_length != 8 or len(salt) != 8:
            return None

        level = self._uds_to_internal_level(access_level)
        if level < 1 or level > 7:
            return None

        # ws[0x00..0x07]=working, ws[0x08..0x0F]=LFSR state, ws[0x10..0x17]=permuted seed
        ws = bytearray(0x20)

        # Step 1: Permute seed bytes into ws[0x10..0x17]
        ws[0x10] = seed[7]
        ws[0x11] = seed[4]
        ws[0x12] = seed[3]
        ws[0x13] = seed[6]
        ws[0x14] = seed[5]
        ws[0x15] = seed[1]
        ws[0x16] = seed[0]
        ws[0x17] = seed[2]

        # Step 2: LFSR iteration count from permuted seed byte at (0x10 + level)
        lfsr_count = (ws[0x10 + level] & 0x07) + 2

        # Step 3: Generate LFSR initial state from salt
        lfsr_state = bytearray(8)
        self._salt_transform(salt, lfsr_state)
        ws[0x08:0x08 + 8] = lfsr_state[0:8]

        # Step 4: Run LFSR (feedback + rotate) for lfsr_count iterations
        for _ in range(lfsr_count):
            self._compute_lfsr_feedback(ws)
            self._rotate_right_array(ws, 0x08, 8)

        # Step 5: Copy permuted seed to working area
        ws[0x00:0x00 + 8] = ws[0x10:0x10 + 8]

        # Step 6: Feistel-like network - 2 rounds, each with 2 half-rounds
        for _round in range(2):
            # Half-round A: uses ws[0x08..0x0B]
            for i in range(4):
                ws[0x10 + i] ^= ws[0x14 + i]

            rot_count = (ws[level] & 0x03) + 1
            for _ in range(rot_count):
                self._rotate_right_array(ws, 0x10, 4)

            val_a = self._le32_load(ws, 0x10)
            val_b = self._le32_load(ws, 0x08)
            self._le32_store(ws, 0x10, (val_a + val_b) & U32)

            ws[0x14:0x14 + 4] = ws[0x00:0x00 + 4]
            ws[0x00:0x00 + 8] = ws[0x10:0x10 + 8]

            # Half-round B: uses ws[0x0C..0x0F]
            for i in range(4):
                ws[0x10 + i] ^= ws[0x14 + i]

            rot_count = (ws[level] & 0x03) + 1
            for _ in range(rot_count):
                self._rotate_right_array(ws, 0x10, 4)

            val_a = self._le32_load(ws, 0x10)
            val_b = self._le32_load(ws, 0x0C)
            self._le32_store(ws, 0x10, (val_a + val_b) & U32)

            ws[0x14:0x14 + 4] = ws[0x00:0x00 + 4]
            ws[0x00:0x00 + 8] = ws[0x10:0x10 + 8]

        # Step 7: Reverse-permute ws[0x00..0x07] -> output key
        out_key = bytearray(8)
        out_key[0] = ws[3]
        out_key[1] = ws[5]
        out_key[2] = ws[6]
        out_key[3] = ws[1]
        out_key[4] = ws[0]
        out_key[5] = ws[7]
        out_key[6] = ws[4]
        out_key[7] = ws[2]

        return bytes(out_key)
