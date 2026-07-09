"""VolkswagenSA2 seed/key provider — ported from jglim/UnlockECU (MIT, (c) 2020 JinGen Lim).

Source: UnlockECU/Security/VolkswagenSA2.cs

Volkswagen SA2 implementation from https://github.com/bri3d/sa2_seed_key.
The db.json "InstructionTape" ByteArray is a small bytecode program run by a
tiny virtual machine (SA2SeedKey) that transforms the 4-byte seed (loaded into
a 32-bit register) into the 4-byte key.

Parameters (from db.json):
  "InstructionTape" (ByteArray): SA2 bytecode program
"""
from __future__ import annotations

from typing import List, Optional

from ..provider import (
    SecurityProvider, Parameter, U32, BIG,
    param_bytes, bytes_to_int, int_to_bytes,
)


class SA2SeedKey:
    """Faithful port of the SA2SeedKey bytecode interpreter."""

    def __init__(self, tape: bytes, seed: int):
        self.Register = seed & U32
        self.CarryFlag = 0
        self.InstructionTape = bytes(tape)
        self.InstructionPointer = 0
        self.ForPointers: List[int] = []
        self.ForIterations: List[int] = []

    # -- opcode implementations ------------------------------------------- #
    def RegisterShiftLeft(self) -> None:
        self.CarryFlag = self.Register & 0x80000000
        self.Register = (self.Register << 1) & U32
        if self.CarryFlag > 0:
            self.Register |= 1
        self.InstructionPointer += 1

    def RegisterShiftRight(self) -> None:
        self.CarryFlag = self.Register & 1
        self.Register >>= 1
        if self.CarryFlag > 0:
            self.Register |= 0x80000000
        self.InstructionPointer += 1

    def Add(self) -> None:
        self.CarryFlag = 0
        outputRegister = self.Register  # C# long (64-bit signed)
        outputRegister += self.FetchOperand()
        if outputRegister > 0xFFFFFFFF:
            self.CarryFlag = 1
            outputRegister &= 0xFFFFFFFF
        self.Register = outputRegister & U32  # (uint)outputRegister
        self.InstructionPointer += 5

    def Subtract(self) -> None:
        self.CarryFlag = 0
        outputRegister = self.Register  # C# long (64-bit signed)
        outputRegister -= self.FetchOperand()
        # C# compares the signed long against 0xFFFFFFFF; a negative result is
        # < 0xFFFFFFFF so no carry is set, matching the source exactly.
        if outputRegister > 0xFFFFFFFF:
            self.CarryFlag = 1
            outputRegister &= 0xFFFFFFFF
        self.Register = outputRegister & U32  # (uint)outputRegister
        self.InstructionPointer += 5

    def ExclusiveOr(self) -> None:
        op = self.FetchOperand()
        self.Register = (self.Register ^ op) & U32
        self.InstructionPointer += 5

    def LoopInit(self) -> None:
        self.ForIterations.insert(0, self.FetchOperandByte() - 1)
        self.InstructionPointer += 2
        self.ForPointers.insert(0, self.InstructionPointer)

    def LoopNext(self) -> None:
        if self.ForIterations[0] > 0:
            self.ForIterations[0] -= 1
            self.InstructionPointer = self.ForPointers[0]
        else:
            self.ForIterations.pop(0)
            self.ForPointers.pop(0)
            self.InstructionPointer += 1

    def BranchConditional(self) -> None:
        skipCount = (self.FetchOperandByte() + 2) & U32
        if self.CarryFlag == 0:
            self.InstructionPointer += skipCount
        else:
            self.InstructionPointer += 2

    def BranchUnconditional(self) -> None:
        self.InstructionPointer += (self.FetchOperandByte() + 2) & U32

    def EndExecution(self) -> None:
        self.InstructionPointer += 1

    # -- operand fetch ---------------------------------------------------- #
    def FetchOperand(self) -> int:
        # InstructionTape.Skip(IP+1).Take(4) — may return fewer than 4 bytes at
        # the tape tail; index into operands[0..3] then would throw in C#, but
        # well-formed tapes always have 4 operand bytes present.
        start = self.InstructionPointer + 1
        operands = self.InstructionTape[start:start + 4]
        interpretedInt = (
            (operands[0] << 24)
            | (operands[1] << 16)
            | (operands[2] << 8)
            | operands[3]
        ) & U32
        return interpretedInt

    def FetchOperandByte(self) -> int:
        return self.InstructionTape[self.InstructionPointer + 1]

    # -- main loop -------------------------------------------------------- #
    def Execute(self) -> int:
        instructionSet = {
            0x81: self.RegisterShiftLeft,
            0x82: self.RegisterShiftRight,
            0x93: self.Add,
            0x84: self.Subtract,
            0x87: self.ExclusiveOr,
            0x68: self.LoopInit,
            0x49: self.LoopNext,
            0x4A: self.BranchConditional,
            0x6B: self.BranchUnconditional,
            0x4C: self.EndExecution,
        }
        while self.InstructionPointer < len(self.InstructionTape):
            instructionSet[self.InstructionTape[self.InstructionPointer]]()
        return self.Register & U32


class VolkswagenSA2(SecurityProvider):
    NAME = "VolkswagenSA2"

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        tape = param_bytes(parameters, "InstructionTape")

        if (len(seed) != 4) or (key_length != 4):
            return None

        sk = SA2SeedKey(tape, bytes_to_int(seed, BIG, 0))
        out_key = bytearray(int_to_bytes(sk.Execute(), BIG))
        return bytes(out_key)
