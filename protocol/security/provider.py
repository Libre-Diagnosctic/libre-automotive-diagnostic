"""Seed/key security-provider foundation — ported from jglim/UnlockECU.

This is a faithful Python port of ``SecurityProvider`` + ``BitUtility`` from
UnlockECU (https://github.com/jglim/UnlockECU, MIT, (c) 2020 JinGen Lim). The
original discovers providers by reflection and calls
``GenerateKey(inSeed, outKey, accessLevel, parameters)``; here each provider
subclasses :class:`SecurityProvider`, sets ``NAME``, and implements
:meth:`generate_key` returning the key bytes (or ``None`` on failure).

Fidelity notes (C# -> Python):
  * C# ``uint`` wraps mod 2**32 — every 32-bit result is masked ``& U32``.
  * C# ``byte`` wraps mod 256 — byte results are masked ``& 0xFF``.
  * ``GetParameterInteger`` parses an *Int32* (signed); ``GetParameterLong`` an
    *Int64* (signed); ``GetParameterByte`` a byte; ``GetParameterBytearray`` hex.
  * Endianness is explicit (:data:`BIG` / :data:`LITTLE`), matching the source.

The seed/key algorithms and the ``db.json`` parameter set are reverse-engineered
and contain no proprietary binary blobs (see the UnlockECU README).
"""
from __future__ import annotations

from typing import List, Optional

U32 = 0xFFFFFFFF
BIG = "big"
LITTLE = "little"


# --------------------------------------------------------------------------- #
#  Parameters — the per-definition constants from db.json
# --------------------------------------------------------------------------- #
class Parameter:
    """One ``{Key, Value, DataType}`` entry from a db.json definition."""

    __slots__ = ("key", "value", "data_type", "access_level")

    def __init__(self, key: str, value: str, data_type: str, access_level: int = -1):
        self.key = key
        self.value = value
        self.data_type = data_type
        self.access_level = access_level

    @classmethod
    def from_dict(cls, d: dict) -> "Parameter":
        return cls(d.get("Key", ""), d.get("Value", ""), d.get("DataType", ""))


class ParameterError(KeyError):
    """A requested parameter (key + type) was not present."""


def _find(parameters: List[Parameter], key: str, data_type: str) -> str:
    for row in parameters:
        if row.key == key and row.data_type == data_type:
            return row.value
    raise ParameterError(f"Failed to fetch {data_type} parameter for key: {key}")


def param_byte(parameters: List[Parameter], key: str) -> int:
    """Hex ``Byte`` parameter -> 0..255 (C# ``GetParameterByte``)."""
    return int(_find(parameters, key, "Byte"), 16) & 0xFF


def param_int(parameters: List[Parameter], key: str) -> int:
    """Hex ``Int32`` parameter -> signed 32-bit int (C# ``GetParameterInteger``)."""
    v = int(_find(parameters, key, "Int32"), 16) & U32
    return v - 0x100000000 if v >= 0x80000000 else v


def param_long(parameters: List[Parameter], key: str) -> int:
    """Hex ``Int64`` parameter -> signed 64-bit int (C# ``GetParameterLong``)."""
    v = int(_find(parameters, key, "Int64"), 16) & 0xFFFFFFFFFFFFFFFF
    return v - 0x10000000000000000 if v >= 0x8000000000000000 else v


def param_bytes(parameters: List[Parameter], key: str) -> bytes:
    """Hex ``ByteArray`` parameter -> bytes (C# ``GetParameterBytearray``)."""
    return bytes_from_hex(_find(parameters, key, "ByteArray"))


# --------------------------------------------------------------------------- #
#  BitUtility + SecurityProvider statics (faithful ports)
# --------------------------------------------------------------------------- #
def bytes_from_hex(hex_string: str) -> bytes:
    """``"AA BB"`` / ``"AABB"`` -> ``b"\\xaa\\xbb"`` (BitUtility.BytesFromHex)."""
    return bytes.fromhex(hex_string.replace(" ", ""))


def bytes_to_hex(data: bytes, spaced: bool = False) -> str:
    sep = " " if spaced else ""
    return sep.join(f"{b:02X}" for b in data)


def pad_bytes(data: bytes, final_size: int) -> bytes:
    """Zero-pad up to ``final_size`` (BitUtility.PadBytes); never truncates."""
    if len(data) >= final_size:
        return bytes(data)
    return bytes(data) + b"\x00" * (final_size - len(data))


def memset(value: int, length: int) -> bytearray:
    return bytearray([value & 0xFF]) * length


def bytes_to_int(data: bytes, endian: str = BIG, offset: int = 0) -> int:
    """Read 4 bytes as an unsigned 32-bit int (SecurityProvider.BytesToInt)."""
    return int.from_bytes(bytes(data[offset:offset + 4]), endian) & U32


def int_to_bytes(value: int, endian: str = BIG) -> bytes:
    """Unsigned 32-bit int -> 4 bytes (SecurityProvider.IntToBytes)."""
    return (value & U32).to_bytes(4, endian)


def get_bit(byte: int, bit_position: int) -> int:
    if bit_position > 7:
        raise ValueError("Attempted to shift beyond 8 bits in a byte")
    return (byte >> bit_position) & 1


def set_bit(byte: int, bit_position: int) -> int:
    if bit_position > 7:
        raise ValueError("Attempted to shift beyond 8 bits in a byte")
    return (byte | (1 << bit_position)) & 0xFF


def get_byte(value: int, byte_position: int) -> int:
    if byte_position > 3:
        raise ValueError("Attempted to shift beyond 4 bytes in an uint")
    return (value >> (8 * byte_position)) & 0xFF


def set_byte(value: int, byte_to_set: int, byte_position: int) -> int:
    if byte_position > 3:
        raise ValueError("Attempted to shift beyond 4 bytes in an uint")
    shift = 8 * byte_position
    value &= ~(0xFF << shift) & U32
    value |= (byte_to_set & 0xFF) << shift
    return value & U32


def rotate_left(val: int, count: int) -> int:
    """32-bit left rotate (SecurityProvider.RotateLeft)."""
    val &= U32
    count %= 32
    if count == 0:
        return val
    return ((val << count) | (val >> (32 - count))) & U32


def rotate_right(val: int, count: int) -> int:
    """32-bit right rotate (SecurityProvider.RotateRight)."""
    val &= U32
    count %= 32
    if count == 0:
        return val
    return ((val >> count) | (val << (32 - count))) & U32


def count_ones(val: int) -> int:
    return bin(val & U32).count("1")


def expand_nibbles(data: bytes) -> bytes:
    """Each byte -> two nibble bytes (SecurityProvider.ExpandByteArrayToNibbles)."""
    out = bytearray()
    for b in data:
        out.append((b >> 4) & 0xF)
        out.append(b & 0xF)
    return bytes(out)


def collapse_nibbles(data: bytes) -> bytes:
    """Two nibble bytes -> one byte (SecurityProvider.CollapseByteArrayFromNibbles)."""
    if len(data) % 2 != 0:
        raise ValueError("Attempted to form a byte array from an odd-numbered set of nibbles.")
    out = bytearray()
    for i in range(0, len(data), 2):
        out.append(((data[i] << 4) | data[i + 1]) & 0xFF)
    return bytes(out)


# --------------------------------------------------------------------------- #
#  Base provider
# --------------------------------------------------------------------------- #
class SecurityProvider:
    """Base class for a seed/key algorithm (UnlockECU ``SecurityProvider``).

    Subclasses set :attr:`NAME` (the ``Provider`` string used in db.json) and
    override :meth:`generate_key`. The utilities above are exposed as static
    methods so ported algorithms can call ``self.bytes_to_int(...)`` etc. and
    read almost 1:1 against the C# source.
    """

    NAME: str = "SecurityProvider"

    def name(self) -> str:
        return self.NAME

    def generate_key(
        self,
        seed: bytes,
        key_length: int,
        access_level: int,
        parameters: List[Parameter],
    ) -> Optional[bytes]:
        """Compute the key for ``seed``. Return the key bytes, or ``None`` on failure.

        ``key_length`` is the expected output length (db.json ``KeyLength``), so
        ports of algorithms that validate ``outKey.Length`` can check it.
        """
        raise NotImplementedError("generate_key was not overridden")

    # -- utilities re-exported as static methods (see module functions) --------
    U32 = U32
    BIG = BIG
    LITTLE = LITTLE

    param_byte = staticmethod(param_byte)
    param_int = staticmethod(param_int)
    param_long = staticmethod(param_long)
    param_bytes = staticmethod(param_bytes)
    bytes_from_hex = staticmethod(bytes_from_hex)
    bytes_to_hex = staticmethod(bytes_to_hex)
    pad_bytes = staticmethod(pad_bytes)
    memset = staticmethod(memset)
    bytes_to_int = staticmethod(bytes_to_int)
    int_to_bytes = staticmethod(int_to_bytes)
    get_bit = staticmethod(get_bit)
    set_bit = staticmethod(set_bit)
    get_byte = staticmethod(get_byte)
    set_byte = staticmethod(set_byte)
    rotate_left = staticmethod(rotate_left)
    rotate_right = staticmethod(rotate_right)
    count_ones = staticmethod(count_ones)
    expand_nibbles = staticmethod(expand_nibbles)
    collapse_nibbles = staticmethod(collapse_nibbles)
