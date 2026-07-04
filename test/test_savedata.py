from kkloader import KoikatuSaveData, SummerVacationSaveData

import pytest


def test_savedata_vanilla(data_dir, tmp_path):
    with open(data_dir / "kk_savedata.dat", "rb") as f:
        raw_data = f.read()
    ks = KoikatuSaveData.load(data_dir / "kk_savedata.dat")
    out_path = tmp_path / "kk_savedata.dat"
    ks.save(str(out_path))
    ks2 = KoikatuSaveData.load(str(out_path))
    assert raw_data == bytes(ks)
    assert bytes(ks) == bytes(ks2)


def test_summervacation_savedata(data_dir, tmp_path):
    with open(data_dir / "sv_savedata.dat", "rb") as f:
        raw_data = f.read()
    svsd = SummerVacationSaveData.load(data_dir / "sv_savedata.dat")
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
