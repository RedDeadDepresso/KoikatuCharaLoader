"""Honeycome character data loader and saver."""

import io
import struct
from functools import partial
from typing import Any, ClassVar

from kkloader.funcs import load_length, load_type, msg_pack, msg_unpack
from kkloader.KoikatuCharaData import About, BlockData, KoikatuCharaData, Parameter, Status
from kkloader.KoikatuCharaData import CoordinateEntry as KoikatuCoordinateEntry
from kkloader.KoikatuCharaData import Custom as KoikatuCustom


class HoneycomeCharaData(KoikatuCharaData):
    """Character data class for Honeycome and Honeycome Party.

    Extends KoikatuCharaData with Honeycome-specific block types including
    Custom (face/body only), Coordinate (with hair/nail), Graphic, and
    game-specific parameters.
    """

    pass


class Custom(KoikatuCustom):
    """Block data for Honeycome custom character appearance (face, body only).

    Unlike Koikatu's Custom which includes hair, Honeycome handles hair
    in the Coordinate block.
    """

    fields: ClassVar[list[str]] = ["face", "body"]


COORDINATE_FIELDS = [
    "clothes",
    "accessory",
    "makeup",
    "hair",
    "nail",
]


def unpack_coordinate(data: bytes, fields: list[str]) -> dict[str, Any]:
    """Deserialize a single coordinate (outfit) payload.

    Args:
        data: Raw bytes of one coordinate.
        fields: Field names stored in the payload, in order.

    Returns:
        Dictionary of the coordinate contents.
    """
    data_stream = io.BytesIO(data)
    return {f: msg_unpack(load_length(data_stream, "i")) for f in fields}


def pack_coordinate(coordinate: dict[str, Any], fields: list[str]) -> bytes:
    """Serialize a single coordinate (outfit) payload.

    Args:
        coordinate: Dictionary of the coordinate contents.
        fields: Field names to write, in order.

    Returns:
        Binary representation of the coordinate.
    """
    pack = struct.Struct("i")
    parts: list[bytes] = []
    for f in fields:
        serialized, length = msg_pack(coordinate[f])
        parts.extend([pack.pack(length), serialized])
    return b"".join(parts)


class CoordinateEntry(KoikatuCoordinateEntry):
    """A standalone Honeycome coordinate (outfit) file.

    Coordinate files carry their own header (【HCClothes】), version, the sex
    the outfit belongs to and a coordinate name, followed by the same payload
    that each element of a character's `Coordinate` block holds.

    The field names follow `Character.HumanDataCoordinate` in the game binary,
    where the file is written by `SaveFile(path, sex)`.
    """

    default_product_no = 200
    default_header = "【HCClothes】".encode()
    default_version = b"0.0.0"
    fields: ClassVar[list[str]] = COORDINATE_FIELDS

    def __init__(self) -> None:
        """Initialize an empty CoordinateEntry."""
        super().__init__()
        self.sex: int = 1

    def _load_extra_header(self, stream: io.BytesIO) -> None:
        """Read the sex byte placed after the version string.

        Args:
            stream: Binary stream positioned right after the version string.
        """
        self.sex = load_type(stream, "B")

    def _make_extra_header(self, stream: io.BytesIO) -> None:
        """Write the sex byte placed after the version string.

        Args:
            stream: Binary stream positioned right after the version string.
        """
        stream.write(struct.pack("B", self.sex))

    def _unpack_payload(self, data: bytes) -> dict[str, Any]:
        """Deserialize the coordinate payload that follows the header.

        Args:
            data: Raw bytes of the payload.

        Returns:
            Dictionary of the coordinate contents.
        """
        return unpack_coordinate(data, self.fields)

    def _pack_payload(self) -> bytes:
        """Serialize the coordinate payload that follows the header.

        Returns:
            Binary representation of the coordinate contents.
        """
        return pack_coordinate(self.data, self.fields)  # type: ignore[arg-type]


class Coordinate(BlockData):
    """Block data for Honeycome coordinate (outfit) information.

    Includes clothes, accessories, makeup, hair, and nail data.

    Attributes:
        fields: List of field names in each coordinate.
    """

    fields: ClassVar[list[str]] = COORDINATE_FIELDS

    def __init__(self, data: bytes | None, version: str) -> None:
        """Initialize a Honeycome Coordinate block data instance.

        Args:
            data: Raw bytes containing the coordinate data, or None.
            version: The version string of this block.
        """
        self.name = "Coordinate"
        self.version = version
        if data is None:
            self.data = None
            return

        self.data: list[dict[str, Any]] | None = [unpack_coordinate(c, self.fields) for c in msg_unpack(data)]

    def serialize(self) -> tuple[bytes, str, str]:
        """Serialize the coordinate data to bytes.

        Returns:
            A tuple of (serialized_data, name, version).
        """
        serialized_all, _ = msg_pack([pack_coordinate(c, self.fields) for c in self.data])  # type: ignore[union-attr]

        return serialized_all, self.name, self.version


Graphic = partial(BlockData, name="Graphic")
GameParameter_HCP = partial(BlockData, name="GameParameter_HCP")
GameInfo_HCP = partial(BlockData, name="GameInfo_HCP")
GameParameter_HC = partial(BlockData, name="GameParameter_HC")
GameInfo_HC = partial(BlockData, name="GameInfo_HC")


HoneycomeCharaData.MODULES = {
    "Custom": Custom,
    "Coordinate": Coordinate,
    "Parameter": Parameter,
    "Status": Status,
    "Graphic": Graphic,
    "About": About,
    "GameParameter_HCP": GameParameter_HCP,
    "GameInfo_HCP": GameInfo_HCP,
    "GameParameter_HC": GameParameter_HC,
    "GameInfo_HC": GameInfo_HC,
}
