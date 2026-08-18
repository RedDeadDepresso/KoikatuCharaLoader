"""Aicomi character data loader and saver."""

from functools import partial

from kkloader.HoneycomeCharaData import Coordinate, Custom, Graphic
from kkloader.HoneycomeCharaData import CoordinateEntry as HoneycomeCoordinateEntry
from kkloader.KoikatuCharaData import About, BlockData, KoikatuCharaData, Parameter, Status


class AicomiCharaData(KoikatuCharaData):
    """Character data class for Aicomi.

    Extends KoikatuCharaData with Aicomi-specific block types,
    reusing Custom, Coordinate, and Graphic from HoneycomeCharaData.
    """

    pass


class CoordinateEntry(HoneycomeCoordinateEntry):
    """A standalone Aicomi coordinate (outfit) file.

    Same layout as the Honeycome one, with the 【ACClothes】 header.
    """

    default_product_no = 100
    default_header = "【ACClothes】".encode()


GameParameter_AC = partial(BlockData, name="GameParameter_AC")
GameInfo_AC = partial(BlockData, name="GameInfo_AC")


AicomiCharaData.MODULES = {
    "Custom": Custom,
    "Coordinate": Coordinate,
    "Parameter": Parameter,
    "Status": Status,
    "Graphic": Graphic,
    "About": About,
    "GameParameter_AC": GameParameter_AC,
    "GameInfo_AC": GameInfo_AC,
}
