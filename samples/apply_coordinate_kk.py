import argparse

from kkloader import KoikatuCharaData
from kkloader.KoikatuCharaData import CoordinateEntry

COORDINATE_TYPES = ["School01", "School02", "Gym", "Swim", "Club", "Plain", "Pajamas"]


def apply_coordinate(chara, coordinate, slot):
    """
    Overwrite one coordinate slot of a Koikatu character card.

    A CoordinateEntry holds exactly the same payload as one element of the
    character's Coordinate block, so it can be assigned as-is.
    """
    chara["Coordinate"].data[slot] = coordinate.data


def main():
    slots = ", ".join("{}={}".format(i, name) for i, name in enumerate(COORDINATE_TYPES))
    parser = argparse.ArgumentParser(description="Put a Koikatu coordinate file on a Koikatu character card.")
    parser.add_argument("chara", help="Koikatu character card (.png)")
    parser.add_argument("coordinate", help="Koikatu coordinate file (.png)")
    parser.add_argument("output", help="output character card (.png)")
    parser.add_argument(
        "--slot",
        type=int,
        default=0,
        choices=range(len(COORDINATE_TYPES)),
        metavar="N",
        help="coordinate slot to overwrite ({}), default: 0".format(slots),
    )
    args = parser.parse_args()

    chara = KoikatuCharaData.load(args.chara)
    coordinate = CoordinateEntry.load(args.coordinate, contains_png=True)

    print(chara)
    print(coordinate)
    print("slot: {} ({})".format(args.slot, COORDINATE_TYPES[args.slot]))

    apply_coordinate(chara, coordinate, args.slot)
    chara.save(args.output)


if __name__ == "__main__":
    main()
