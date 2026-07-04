"""Amanatsu Location character data loader and saver."""

import io
import struct
from functools import partial
from typing import Any

from kkloader.funcs import get_png, load_length, load_type, msg_pack, msg_unpack, read_lstinfo_blocks, to_stream, write_lstinfo_blocks
from kkloader.HoneycomeCharaData import Custom, Graphic
from kkloader.KoikatuCharaData import About, BlockData, KoikatuCharaData, Parameter, Status


class AmanatsuCharaData(KoikatuCharaData):
    """Character data class for Amanatsu Location (甘夏ろけーしょん).

    Extends KoikatuCharaData with Amanatsu Location-specific block types.
    Reuses Custom and Graphic from HoneycomeCharaData.
    """

    pass


class CoordinateEntry:
    """A single coordinate (outfit) entry with nested lstInfo block structure.

    Each entry has its own header (【ALClothes】), version, and sub-blocks
    (Clothes, Accessory, Hair, FaceMakeup, BodyMakeup, About).
    """

    def __init__(self) -> None:
        """Initialize an empty CoordinateEntry."""
        self.image: bytes | None = None
        self.product_no: int = 0
        self.header: bytes = b""
        self.version: bytes = b""
        self.unknown: bytes = b"\x00\x00"
        self.blockdata: list[str] = []
        self.original_file_path: str | None = None
        self.original_lstinfo_order: list[str] = []
        self.serialized_lstinfo_order: list[str] = []

    @classmethod
    def load(cls, filelike: str | bytes | io.BytesIO, contains_png: bool = False) -> "CoordinateEntry":
        """Load a coordinate entry from a file, bytes, or BytesIO stream.

        Args:
            filelike: Path to a coordinate file, raw bytes, or BytesIO stream.
            contains_png: Whether the input contains a PNG image header.

        Returns:
            A CoordinateEntry instance with loaded data.
        """
        entry = cls()
        stream, entry.original_file_path = to_stream(filelike)

        if contains_png:
            entry.image = get_png(stream)

        entry.product_no = load_type(stream, "i")
        entry.header = load_length(stream, "b")
        entry.version = load_length(stream, "b")
        entry.unknown = stream.read(2)

        raw_payload, entries, entry.original_lstinfo_order, entry.serialized_lstinfo_order = read_lstinfo_blocks(stream)

        entry.blockdata = []
        for e in entries:
            name = e["name"]
            block_data = raw_payload[e["pos"] : e["pos"] + e["size"]]
            entry.blockdata.append(name)
            setattr(entry, name, BlockData(name=name, data=block_data, version=e["version"]))

        return entry

    def save(self, filename: str) -> None:
        """Save the coordinate entry to a file.

        Args:
            filename: Path to write the coordinate file.
        """
        with open(filename, "bw") as f:
            if self.image is not None:
                f.write(self.image)
            f.write(bytes(self))

    def __bytes__(self) -> bytes:
        """Serialize the coordinate entry to bytes (without PNG image).

        Returns:
            Binary representation of the coordinate entry.
        """
        lstinfo_bytes = write_lstinfo_blocks(self, self.serialized_lstinfo_order, self.original_lstinfo_order)

        bpack = struct.Struct("b")
        parts = [
            struct.Struct("i").pack(self.product_no),
            bpack.pack(len(self.header)),
            self.header,
            bpack.pack(len(self.version)),
            self.version,
            self.unknown,
            lstinfo_bytes,
        ]
        return b"".join(parts)

    def jsonalizable(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the coordinate entry.

        Returns:
            Dictionary of sub-block data.
        """
        result: dict[str, Any] = {}
        for name in self.blockdata:
            result[name] = getattr(self, name).jsonalizable()
        return result


class Coordinate(BlockData):
    """Block data for Amanatsu Location coordinate (outfit) information.

    Each coordinate entry is a nested lstInfo-based structure with its own
    header (【ALClothes】) and sub-blocks (Clothes, Accessory, Hair,
    FaceMakeup, BodyMakeup, About).
    """

    def __init__(self, data: bytes | None, version: str) -> None:
        """Initialize an Amanatsu Location Coordinate block data instance.

        Args:
            data: Raw bytes containing the coordinate data, or None.
            version: The version string of this block.
        """
        self.name = "Coordinate"
        self.version = version
        if data is None:
            self.data = None
            return

        self.data: list[CoordinateEntry] | None = []
        for coordinate_bytes in msg_unpack(data):
            self.data.append(CoordinateEntry.load(coordinate_bytes))

    def serialize(self) -> tuple[bytes, str, str]:
        """Serialize the coordinate data to bytes.

        Returns:
            A tuple of (serialized_data, name, version).
        """
        entries: list[bytes] = []
        for entry in self.data:  # type: ignore[union-attr]
            entries.append(bytes(entry))
        serialized, _ = msg_pack(entries)
        return serialized, self.name, self.version

    def jsonalizable(self) -> Any:
        """Return a JSON-serializable representation of the data.

        Returns:
            List of coordinate entry dictionaries.
        """
        if self.data is None:
            return None
        return [entry.jsonalizable() for entry in self.data]


GameParameter_AL = partial(BlockData, name="GameParameter_AL")
GameInfo_AL = partial(BlockData, name="GameInfo_AL")
ThumbParameter = partial(BlockData, name="ThumbParameter")


AmanatsuCharaData.MODULES = {
    "Custom": Custom,
    "Coordinate": Coordinate,
    "Parameter": Parameter,
    "Status": Status,
    "Graphic": Graphic,
    "About": About,
    "GameParameter_AL": GameParameter_AL,
    "GameInfo_AL": GameInfo_AL,
    "ThumbParameter": ThumbParameter,
}
