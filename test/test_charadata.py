import json
import os
import re
from pathlib import Path

from kkloader import (
    AicomiCharaData,
    AmanatsuCharaData,
    EmocreCharaData,
    HoneycomeCharaData,
    KoikatuCharaData,
    SummerVacationCharaData,
)
from kkloader.AmanatsuCharaData import CoordinateEntry
from kkloader.KoikatuCharaHeader import KoikatuCharaHeader

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_IMAGE_SUMMARY_RE = re.compile(r"^\[(PNG|JPEG) image, [\d,]+ bytes, md5:[0-9a-f]{32}\]$")


def test_load_character(data_dir):
    kc = KoikatuCharaData.load(data_dir / "kk_chara.png")
    assert hasattr(kc, "Custom")
    assert hasattr(kc, "Coordinate")
    assert hasattr(kc, "Parameter")
    assert hasattr(kc, "Status")
    assert kc.original_file_path == os.path.abspath(data_dir / "kk_chara.png")


def test_load_character_from_bytes_has_no_original_file_path(data_dir):
    with open(data_dir / "kk_chara.png", "rb") as f:
        raw_data = f.read()
    kc = KoikatuCharaData.load(raw_data)
    assert kc.original_file_path is None


def test_load_sunshine_character(data_dir):
    kc = KoikatuCharaData.load(data_dir / "kks_chara.png")
    assert hasattr(kc, "Custom")
    assert hasattr(kc, "Coordinate")
    assert hasattr(kc, "Parameter")
    assert hasattr(kc, "Status")
    assert hasattr(kc, "About")


def test_load_emocre_character(data_dir):
    ec = EmocreCharaData.load(data_dir / "ec_chara.png")
    assert hasattr(ec, "Custom")
    assert hasattr(ec, "Coordinate")
    assert hasattr(ec, "Parameter")
    assert hasattr(ec, "Status")


def test_load_mod_character(data_dir):
    kc = KoikatuCharaData.load(data_dir / "kk_mod_chara.png")
    assert hasattr(kc, "Custom")
    assert hasattr(kc, "Coordinate")
    assert hasattr(kc, "Parameter")
    assert hasattr(kc, "Status")
    assert hasattr(kc, "KKEx")


@pytest.mark.parametrize(
    "loader, filename",
    [
        (HoneycomeCharaData, "hcp_chara.png"),
        (HoneycomeCharaData, "hc_chara.png"),
        (SummerVacationCharaData, "sv_chara.png"),
        (AicomiCharaData, "ac_chara.png"),
        (AmanatsuCharaData, "al_chara.png"),
    ],
    ids=["hcp", "hc", "sv", "ac", "al"],
)
def test_load_blocks_in_modules(loader, filename, data_dir):
    chara = loader.load(data_dir / filename)
    for b in chara.blockdata:
        assert b in chara.modules.keys()


SAVE_CASES = [
    (KoikatuCharaData, "kk_chara.png", ["nickname"]),
    (KoikatuCharaData, "kks_chara.png", ["nickname"]),
    (KoikatuCharaData, "kk_mod_chara.png", ["nickname"]),
    (EmocreCharaData, "ec_chara.png", ["fullname"]),
    (HoneycomeCharaData, "hcp_chara.png", ["lastname", "firstname"]),
    (HoneycomeCharaData, "hc_chara.png", ["lastname", "firstname"]),
    (SummerVacationCharaData, "sv_chara.png", ["lastname", "firstname"]),
    (AicomiCharaData, "ac_chara.png", ["lastname", "firstname"]),
    (AmanatsuCharaData, "al_chara.png", ["lastname", "firstname"]),
]


@pytest.mark.parametrize("loader, filename, name_fields", SAVE_CASES, ids=[c[1] for c in SAVE_CASES])
def test_save_roundtrip(loader, filename, name_fields, data_dir, tmp_path):
    with open(data_dir / filename, "rb") as f:
        raw_data = f.read()
    chara1 = loader.load(data_dir / filename)
    out_path = tmp_path / filename
    chara1.save(str(out_path))
    chara2 = loader.load(str(out_path))
    for field in name_fields:
        assert chara1["Parameter"][field] == chara2["Parameter"][field]
    assert raw_data == bytes(chara1)
    assert bytes(chara1) == bytes(chara2)


@pytest.mark.parametrize("chara_path", [str(p) for p in (DATA_DIR / "testing-data").glob("*.png")])
def test_save_modding_character_param(chara_path, request, tmp_path):
    if not request.config.getoption("--run-optional"):
        pytest.skip("requires `--run-optional` to run")

    print("=" * 20)
    print(f"Testing {chara_path}")
    with open(chara_path, "rb") as f:
        raw_data = f.read()

    out_path = tmp_path / Path(chara_path).name
    kc = KoikatuCharaData.load(chara_path)
    kc.save(str(out_path))
    kc2 = KoikatuCharaData.load(str(out_path))

    assert kc["Parameter"]["nickname"] == kc2["Parameter"]["nickname"]
    assert bytes(kc) == bytes(kc2)
    assert raw_data == bytes(kc)
    assert raw_data == bytes(kc2)


JSON_CASES = [
    (KoikatuCharaData, "kk_chara.png"),
    (KoikatuCharaData, "kks_chara.png"),
    (EmocreCharaData, "ec_chara.png"),
    (HoneycomeCharaData, "hcp_chara.png"),
    (HoneycomeCharaData, "hc_chara.png"),
    (SummerVacationCharaData, "sv_chara.png"),
    (AicomiCharaData, "ac_chara.png"),
    (AmanatsuCharaData, "al_chara.png"),
]


@pytest.mark.parametrize("loader, filename", JSON_CASES, ids=[c[1] for c in JSON_CASES])
def test_save_json(loader, filename, data_dir, tmp_path):
    chara = loader.load(data_dir / filename)
    out_path = tmp_path / f"{filename}.json"
    chara.save_json(str(out_path))


def _assert_common_repr_fields(chara_data, expected_name):
    repr_text = repr(chara_data)
    assert f"product_no={chara_data.product_no!r}" in repr_text
    assert f"header={chara_data.header.decode('utf-8')!r}" in repr_text
    assert f"version={chara_data.version.decode('utf-8')!r}" in repr_text
    assert f"name={expected_name!r}" in repr_text
    assert f"blocks={chara_data.blockdata!r}" in repr_text
    assert f"has_kkex={'KKEx' in chara_data.blockdata}" in repr_text
    assert f"original_file_path={chara_data.original_file_path!r}" in repr_text


def _expected_repr_name(chara_data):
    param = chara_data["Parameter"].data
    fullname = str(param.get("fullname", "")).strip()
    if fullname:
        return fullname
    lastname = str(param.get("lastname", "")).strip()
    firstname = str(param.get("firstname", "")).strip()
    nickname = str(param.get("nickname", "")).strip()
    name = "{} {}".format(lastname, firstname).strip()
    if nickname:
        return "{} ( {} )".format(name, nickname).strip()
    return name


def test_repr_koikatu_fields(data_dir):
    kc = KoikatuCharaData.load(data_dir / "kk_chara.png")
    expected_name = _expected_repr_name(kc)
    _assert_common_repr_fields(kc, expected_name)


def test_repr_mod_character_has_kkex(data_dir):
    kc = KoikatuCharaData.load(data_dir / "kk_mod_chara.png")
    assert "has_kkex=True" in repr(kc)


def test_repr_emocre_name(data_dir):
    ec = EmocreCharaData.load(data_dir / "ec_chara.png")
    expected_name = _expected_repr_name(ec)
    _assert_common_repr_fields(ec, expected_name)
    repr_text = repr(ec)
    assert f"userid={ec.userid.decode('utf-8')!r}" in repr_text
    assert f"dataid={ec.dataid.decode('utf-8')!r}" in repr_text


def test_repr_sunshine_contains_about_guids(data_dir):
    kks = KoikatuCharaData.load(data_dir / "kks_chara.png")
    repr_text = repr(kks)
    assert f"userid={kks['About']['userID']!r}" in repr_text
    assert f"dataid={kks['About']['dataID']!r}" in repr_text


def test_repr_honeycome_like_name_and_about_guids(data_dir):
    for cls, path in [
        (HoneycomeCharaData, data_dir / "hc_chara.png"),
        (SummerVacationCharaData, data_dir / "sv_chara.png"),
        (AicomiCharaData, data_dir / "ac_chara.png"),
        (AmanatsuCharaData, data_dir / "al_chara.png"),
    ]:
        chara = cls.load(path)
        repr_text = repr(chara)
        expected_name = _expected_repr_name(chara)
        _assert_common_repr_fields(chara, expected_name)
        assert f"userid={chara['About']['userID']!r}" in repr_text
        assert f"dataid={chara['About']['dataID']!r}" in repr_text


def test_character_str_falls_back_to_repr(data_dir):
    samples = [
        KoikatuCharaData.load(data_dir / "kk_chara.png"),
        EmocreCharaData.load(data_dir / "ec_chara.png"),
        HoneycomeCharaData.load(data_dir / "hc_chara.png"),
        SummerVacationCharaData.load(data_dir / "sv_chara.png"),
        AicomiCharaData.load(data_dir / "ac_chara.png"),
        AmanatsuCharaData.load(data_dir / "al_chara.png"),
    ]
    for chara in samples:
        assert str(chara) == repr(chara)


def _collect_image_summaries(obj):
    found = []
    if isinstance(obj, dict):
        for v in obj.values():
            found.extend(_collect_image_summaries(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_collect_image_summaries(v))
    elif isinstance(obj, str) and _IMAGE_SUMMARY_RE.match(obj):
        found.append(obj)
    return found


def _has_base64_image(obj):
    if isinstance(obj, dict):
        return any(_has_base64_image(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_base64_image(v) for v in obj)
    if isinstance(obj, str) and len(obj) > 100:
        return obj.startswith("iVBOR") or obj.startswith("/9j/")
    return False


@pytest.mark.parametrize(
    "loader,path",
    [
        (KoikatuCharaData, DATA_DIR / "kk_chara.png"),
        (AmanatsuCharaData, DATA_DIR / "al_chara.png"),
        (SummerVacationCharaData, DATA_DIR / "sv_chara.png"),
    ],
    ids=["kk", "al", "svs"],
)
class TestSaveJsonSummarizeImage:
    def test_summarize_image_default(self, loader, path, tmp_path):
        chara = loader.load(path)
        out_path = tmp_path / "out.json"
        chara.save_json(str(out_path), include_image=True)
        with open(out_path) as f:
            data = json.load(f)
        summaries = _collect_image_summaries(data)
        assert len(summaries) >= 1
        for s in summaries:
            assert _IMAGE_SUMMARY_RE.match(s)
        assert not _has_base64_image(data)

    def test_summarize_image_false(self, loader, path, tmp_path):
        chara = loader.load(path)
        out_path = tmp_path / "out.json"
        chara.save_json(str(out_path), include_image=True, summarize_image=False)
        with open(out_path) as f:
            data = json.load(f)
        summaries = _collect_image_summaries(data)
        assert len(summaries) == 0
        assert _has_base64_image(data)


def test_load_amanatsu_coordinate_structure(data_dir):
    al = AmanatsuCharaData.load(data_dir / "al_chara.png")
    coord = al["Coordinate"]
    assert len(coord.data) == 2
    for entry in coord.data:
        assert "Clothes" in entry.blockdata
        assert "Accessory" in entry.blockdata
        assert "Hair" in entry.blockdata
        assert "FaceMakeup" in entry.blockdata
        assert "BodyMakeup" in entry.blockdata
        assert "About" in entry.blockdata


def test_load_al_coordinate(data_dir):
    entry = CoordinateEntry.load(data_dir / "al_coordinate.png", contains_png=True)
    assert entry.image is not None
    assert entry.header == b"\xe3\x80\x90ALClothes\xe3\x80\x91"
    assert entry.product_no == 100
    assert entry.blockdata == ["Clothes", "Accessory", "Hair", "FaceMakeup", "BodyMakeup", "About"]
    assert entry.original_file_path.endswith("al_coordinate.png")


def test_save_al_coordinate(data_dir, tmp_path):
    with open(data_dir / "al_coordinate.png", "rb") as f:
        raw_data = f.read()
    entry = CoordinateEntry.load(data_dir / "al_coordinate.png", contains_png=True)
    out_path = tmp_path / "al_coordinate.png"
    entry.save(str(out_path))
    with open(out_path, "rb") as f:
        saved_data = f.read()
    assert raw_data == saved_data


def test_load_chara_header(data_dir):
    kch = KoikatuCharaHeader.load(data_dir / "kk_chara.png")
    assert kch.image is not None
    assert kch.product_no == 100
    assert kch.header == b"\xe3\x80\x90KoiKatuChara\xe3\x80\x91"
    assert kch.version is not None
    assert kch.face_image is not None


def test_load_chara_header_from_bytes(data_dir):
    with open(data_dir / "kk_chara.png", "rb") as f:
        raw = f.read()
    kch = KoikatuCharaHeader.load(raw)
    assert kch.product_no == 100
    assert kch.header is not None
