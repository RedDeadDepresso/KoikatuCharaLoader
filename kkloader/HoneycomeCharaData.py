"""Honeycome character data loader and saver."""

import io
import struct
from functools import partial
from typing import Any, ClassVar

from kkloader.funcs import load_length, msg_pack, msg_unpack
from kkloader.KoikatuCharaData import About, BlockData, KoikatuCharaData, Parameter, Status
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


class Coordinate(BlockData):
    """Block data for Honeycome coordinate (outfit) information.

    Includes clothes, accessories, makeup, hair, and nail data.

    Attributes:
        fields: List of field names in each coordinate.
    """

    fields: ClassVar[list[str]] = [
        "clothes",
        "accessory",
        "makeup",
        "hair",
        "nail",
    ]

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

        self.data: list[dict[str, Any]] | None = []
        for coordinate_bytes in msg_unpack(data):
            data_stream = io.BytesIO(coordinate_bytes)
            coordinate_dict: dict[str, Any] = {}
            for f in self.fields:
                coordinate_dict[f] = msg_unpack(load_length(data_stream, "i"))
            self.data.append(coordinate_dict)

    def serialize(self) -> tuple[bytes, str, str]:
        """Serialize the coordinate data to bytes.

        Returns:
            A tuple of (serialized_data, name, version).
        """
        data: list[bytes] = []
        for i in self.data:  # type: ignore[union-attr]
            c: list[bytes] = []
            pack = struct.Struct("i")

            for f in self.fields:
                serialized, length = msg_pack(i[f])
                c.extend([pack.pack(length), serialized])

            data.append(b"".join(c))
        serialized_all, _ = msg_pack(data)

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
