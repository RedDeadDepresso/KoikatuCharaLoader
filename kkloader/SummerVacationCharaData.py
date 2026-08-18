"""SummerVacationScramble character data loader and saver."""

from functools import partial

from kkloader.HoneycomeCharaData import Coordinate, Custom, Graphic
from kkloader.HoneycomeCharaData import CoordinateEntry as HoneycomeCoordinateEntry
from kkloader.KoikatuCharaData import About, BlockData, KoikatuCharaData, Parameter, Status


class SummerVacationCharaData(KoikatuCharaData):
    """Character data class for SummerVacationScramble.

    Extends KoikatuCharaData with SummerVacation-specific block types,
    reusing Custom, Coordinate, and Graphic from HoneycomeCharaData.
    """

    pass


class CoordinateEntry(HoneycomeCoordinateEntry):
    """A standalone SummerVacationScramble coordinate (outfit) file.

    Same layout as the Honeycome one, with the 【SVClothes】 header.
    """

    default_product_no = 100
    default_header = "【SVClothes】".encode()


GameParameter_SV = partial(BlockData, name="GameParameter_SV")
GameInfo_SV = partial(BlockData, name="GameInfo_SV")


SummerVacationCharaData.MODULES = {
    "Custom": Custom,
    "Coordinate": Coordinate,
    "Parameter": Parameter,
    "Status": Status,
    "Graphic": Graphic,
    "About": About,
    "GameParameter_SV": GameParameter_SV,
    "GameInfo_SV": GameInfo_SV,
}
