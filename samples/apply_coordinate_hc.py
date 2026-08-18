import argparse

from kkloader import HoneycomeCharaData
from kkloader.HoneycomeCharaData import CoordinateEntry

COORDINATE_TYPES = ["Plain", "Roomwear", "Bathing"]


def apply_coordinate(chara, coordinate, slot):
    """
    Overwrite one coordinate slot of a Honeycome character card.

    A CoordinateEntry holds exactly the same payload as one element of the
    character's Coordinate block, so it can be assigned as-is.
    """
    if coordinate.sex != chara["Parameter"]["sex"]:
        # Honeycome writes the sex into the coordinate file header, and clothes
        # ids are numbered per sex.
        print("warning: the coordinate is for sex={} but the character is sex={}".format(coordinate.sex, chara["Parameter"]["sex"]))

    chara["Coordinate"].data[slot] = coordinate.data


def main():
    slots = ", ".join("{}={}".format(i, name) for i, name in enumerate(COORDINATE_TYPES))
    parser = argparse.ArgumentParser(description="Put a Honeycome coordinate file on a Honeycome character card.")
    parser.add_argument("chara", help="Honeycome character card (.png)")
    parser.add_argument("coordinate", help="Honeycome coordinate file (.png)")
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

    chara = HoneycomeCharaData.load(args.chara)
    coordinate = CoordinateEntry.load(args.coordinate, contains_png=True)

    print(chara)
    print(coordinate)
    print("slot: {} ({})".format(args.slot, COORDINATE_TYPES[args.slot]))

    apply_coordinate(chara, coordinate, args.slot)
    chara.save(args.output)


if __name__ == "__main__":
    main()
