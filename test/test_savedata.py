from kkloader import AicomiSaveData, KoikatuSaveData, SummerVacationSaveData
from kkloader.MemoryPack import MpReader, MpWriter, read_version

import pytest


def test_savedata_vanilla(savedata_dir, tmp_path):
    with open(savedata_dir / "kk_savedata.dat", "rb") as f:
        raw_data = f.read()
    ks = KoikatuSaveData.load(savedata_dir / "kk_savedata.dat")
    out_path = tmp_path / "kk_savedata.dat"
    ks.save(str(out_path))
    ks2 = KoikatuSaveData.load(str(out_path))
    assert raw_data == bytes(ks)
    assert bytes(ks) == bytes(ks2)


def test_summervacation_savedata(savedata_dir, tmp_path):
    with open(savedata_dir / "sv_savedata.dat", "rb") as f:
        raw_data = f.read()
    svsd = SummerVacationSaveData.load(savedata_dir / "sv_savedata.dat")
    out_path = tmp_path / "sv_savedata.dat"
    svsd.save(str(out_path))
    svsd2 = SummerVacationSaveData.load(str(out_path))
    assert svsd.meta["WorldName"] == svsd2.meta["WorldName"]
    assert len(svsd.charas) == len(svsd.chara_details) == len(svsd2.charas) == len(svsd2.chara_details)
    assert raw_data == bytes(svsd)
    assert bytes(svsd) == bytes(svsd2)


def test_savedata_load_invalid_type():
    with pytest.raises(ValueError, match="unsupported input"):
        KoikatuSaveData.load(123)


def test_aicomi_savedata(savedata_dir, tmp_path):
    save_path = savedata_dir / "ac_savedata.dat"
    with open(save_path, "rb") as f:
        raw_data = f.read()
    acs = AicomiSaveData.load(save_path)
    out_path = tmp_path / "ac_savedata.dat"
    acs.save(str(out_path))
    acs2 = AicomiSaveData.load(str(out_path))
    assert raw_data == bytes(acs)
    assert bytes(acs) == bytes(acs2)
    assert len(acs.charas) == 8
    assert acs.player["type"] == "PlayerData"
    assert acs.core["SaveTimeText"] == "2026/07/05 4:50:25"
    assert "相原 結里" in acs.names.values()
    favors = [npc["fields"]["FavorValue"] for npc in acs.npcs if npc is not None]
    assert favors == [0, 0, 0, 0]
    assert [unique["fields"]["FavorValue"] for unique in acs.uniques] == [0, 0, 0]
    assert [unique["index"] for unique in acs.uniques] == [0, 1, 2]


def test_aicomi_savedata_edit_chara(savedata_dir):
    save_path = savedata_dir / "ac_savedata.dat"
    with open(save_path, "rb") as f:
        raw_data = f.read()
    acs = AicomiSaveData.load(save_path)
    acs.player["chara"]["Parameter"]["firstname"] = "検証太郎"
    edited = bytes(acs)
    assert edited != raw_data
    reloaded = AicomiSaveData.load(edited)
    assert bytes(reloaded) == edited
    assert reloaded.player["chara"]["Parameter"]["firstname"] == "検証太郎"


def test_aicomi_savedata_edit_fields(savedata_dir):
    save_path = savedata_dir / "ac_savedata.dat"
    with open(save_path, "rb") as f:
        raw_data = f.read()
    acs = AicomiSaveData.load(save_path)
    npc_index, npc = next((i, n) for i, n in enumerate(acs.npcs) if n is not None)
    npc["fields"]["FavorValue"] = 555
    npc["fields"]["Intimacy"] = 88
    acs.core["SaveTimeText"] = "2026/01/01 00:00:00"
    edited = bytes(acs)
    assert edited != raw_data
    reloaded = AicomiSaveData.load(edited)
    fields = reloaded.npcs[npc_index]["fields"]
    assert fields["FavorValue"] == 555
    assert fields["Intimacy"] == 88
    assert reloaded.core["SaveTimeText"] == "2026/01/01 00:00:00"
    assert bytes(reloaded) == edited


# MemoryPack codec tests (no save-data fixture required)


@pytest.mark.parametrize("value", [None, "", "abc", "2026/03/31 17:01:53", "天宮 心音", "café"])
def test_memorypack_string_roundtrip(value):
    writer = MpWriter()
    writer.string(value)
    reader = MpReader(writer.bytes())
    assert reader.string() == value
    assert reader.pos == len(writer.bytes())


def test_memorypack_object_header():
    assert MpReader(b"\xff").object_header() is None
    assert MpReader(b"\x1d").object_header() == 29


def test_memorypack_version():
    blob = bytes([4]) + b"".join(v.to_bytes(4, "little") for v in (1, 2, 3, 4))
    assert read_version(MpReader(blob)) == {"major": 1, "minor": 2, "build": 3, "revision": 4}
