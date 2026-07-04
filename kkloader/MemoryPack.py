"""A small MemoryPack wire-format reader/writer.

MemoryPack (Cysharp) is the binary serializer used by ILLGAMES titles. This
module implements just enough of the wire format to decode the Aicomi save
records whose field order/type were recovered from the il2cpp dump
(see `kkloader.AicomiSaveData`). It is intentionally partial: value types with
hand-written formatters that we have not reverse-engineered raise
`UndecodableType`, which the caller turns into a raw-bytes fallback so the
overall round-trip stays byte-exact.

Wire format reference (verified against real saves):
  * object header : 1 byte member-count; 0xFF = null object.
  * primitives    : little-endian, natural width.
  * string        : i32 header — -1 null, 0 empty, >0 UTF16 (header code units),
                    <=-2 UTF8 (byteCount = ~header, then i32 utf16-len, then bytes).
  * collection    : i32 count (-1 = null) followed by count elements.
  * System.Version: object with 4x i32 (major, minor, build, revision).
  * varint        : first sbyte in [-120, 127] is the value itself; otherwise
                    it is a type code (-124 = i16, -126 = i32, ... ) followed
                    by that type little-endian. Used by version-tolerant
                    objects for their per-member length table.
"""

from __future__ import annotations

import struct
from typing import Any, Callable

NULL_OBJECT = 0xFF


class UndecodableType(Exception):
    """Raised when a type's wire format is not implemented, so the caller can
    fall back to preserving the remaining bytes raw."""


class MpReader:
    """Sequential reader over a MemoryPack byte buffer."""

    def __init__(self, data: bytes, pos: int = 0) -> None:
        self.data = data
        self.pos = pos

    # -- primitives ---------------------------------------------------------
    def _take(self, n: int) -> bytes:
        b = self.data[self.pos : self.pos + n]
        if len(b) != n:
            raise EOFError(f"want {n} bytes at {self.pos}, have {len(b)}")
        self.pos += n
        return b

    def u8(self) -> int:
        return self._take(1)[0]

    def i8(self) -> int:
        return struct.unpack("<b", self._take(1))[0]

    def boolean(self) -> bool:
        return self._take(1)[0] != 0

    def i16(self) -> int:
        return struct.unpack("<h", self._take(2))[0]

    def u16(self) -> int:
        return struct.unpack("<H", self._take(2))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self._take(8))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self._take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self._take(8))[0]

    # -- object header ------------------------------------------------------
    def object_header(self) -> int | None:
        """Return the member count, or None for a null object."""
        c = self.u8()
        return None if c == NULL_OBJECT else c

    # -- varint ---------------------------------------------------------------
    def varint(self) -> int:
        """MemoryPack VarInt (see module docstring)."""
        code = self.i8()
        if code >= -120:
            return code
        reader = {
            -121: self.u8,
            -122: self.i8,
            -123: self.u16,
            -124: self.i16,
            -125: self.u32,
            -126: self.i32,
            -127: self.u64,
            -128: self.i64,
        }.get(code)
        if reader is None:
            raise ValueError(f"invalid varint type code {code}")
        return reader()

    # -- string -------------------------------------------------------------
    def string(self) -> str | None:
        h = self.i32()
        if h == -1:
            return None
        if h == 0:
            return ""
        if h > 0:
            return self._take(h * 2).decode("utf-16-le")
        byte_count = ~h  # h <= -2
        self.i32()  # utf16 length (unused for decode)
        return self._take(byte_count).decode("utf-8")

    # -- collection header --------------------------------------------------
    def collection_header(self) -> int | None:
        n = self.i32()
        return None if n == -1 else n


# -- primitive reader registry (name -> MpReader method) --------------------
_PRIM: dict[str, Callable[[MpReader], Any]] = {
    "bool": MpReader.boolean,
    "byte": MpReader.u8,
    "sbyte": MpReader.i8,
    "short": MpReader.i16,
    "ushort": MpReader.u16,
    "int": MpReader.i32,
    "uint": MpReader.u32,
    "long": MpReader.i64,
    "ulong": MpReader.u64,
    "float": MpReader.f32,
    "double": MpReader.f64,
    "string": MpReader.string,
}


def read_version(r: MpReader) -> dict | None:
    """System.Version — object header (4) + major/minor/build/revision i32."""
    n = r.object_header()
    if n is None:
        return None
    vals = [r.i32() for _ in range(n)]
    keys = ["major", "minor", "build", "revision"]
    return {keys[i] if i < len(keys) else str(i): v for i, v in enumerate(vals)}


def read_primitive_array(r: MpReader, elem: str) -> list | None:
    n = r.collection_header()
    if n is None:
        return None
    fn = _PRIM[elem]
    return [fn(r) for _ in range(n)]


class MpWriter:
    """Sequential writer producing MemoryPack bytes (mirror of MpReader)."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def raw(self, b: bytes) -> "MpWriter":
        self.buf += b
        return self

    def u8(self, v: int) -> None:
        self.buf += struct.pack("<B", v & 0xFF)

    def i8(self, v: int) -> None:
        self.buf += struct.pack("<b", v)

    def boolean(self, v: bool) -> None:
        self.buf += b"\x01" if v else b"\x00"

    def i32(self, v: int) -> None:
        self.buf += struct.pack("<i", v)

    def u32(self, v: int) -> None:
        self.buf += struct.pack("<I", v)

    def f32(self, v: float) -> None:
        self.buf += struct.pack("<f", v)

    def varint(self, v: int) -> None:
        """MemoryPack VarInt, mirroring `MemoryPackWriter.WriteVarInt(int)`."""
        if -120 <= v <= 127:
            self.i8(v)
        elif -128 <= v <= -121:
            self.i8(-122)
            self.i8(v)
        elif -32768 <= v <= 32767:
            self.i8(-124)
            self.buf += struct.pack("<h", v)
        else:
            self.i8(-126)
            self.buf += struct.pack("<i", v)

    def object_header(self, count: int | None) -> None:
        self.u8(NULL_OBJECT if count is None else count)

    def string(self, s: str | None) -> None:
        if s is None:
            self.i32(-1)
            return
        if s == "":
            self.i32(0)
            return
        b = s.encode("utf-8")
        self.i32(~len(b))
        self.i32(len(s.encode("utf-16-le")) // 2)  # UTF16 code-unit count
        self.buf += b

    def bytes(self) -> bytes:
        return bytes(self.buf)
