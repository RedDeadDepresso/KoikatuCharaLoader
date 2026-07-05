import io
import tempfile

from kkloader import HoneycomeSceneData, KoikatuSceneData
from kkloader.EmocreSceneData import EmocreSceneData

import pytest

# ============================================================
# Koikatu scene tests
# ============================================================


def test_load_simple_scene(data_dir):
    """Test loading a simple Koikatu scene file with one item"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_simple.png")

    assert hasattr(scene_data, "version")
    assert hasattr(scene_data, "objects")
    assert hasattr(scene_data, "map")
    assert scene_data.version == "1.1.2.1"

    assert len(scene_data.objects) == 1

    obj_key = list(scene_data.objects.keys())[0]
    assert scene_data.objects[obj_key]["type"] == 1

    obj_data = scene_data.objects[obj_key]["data"]
    assert "group" in obj_data
    assert "category" in obj_data
    assert "no" in obj_data
    assert "colors" in obj_data
    assert "patterns" in obj_data
    assert "panel" in obj_data


def test_koikatu_scene_repr_fields(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_simple.png")
    repr_text = repr(scene_data)
    assert f"version={scene_data.version!r}" in repr_text
    assert f"original_filename={str((data_dir / 'kk_scene_simple.png').resolve())!r}" in repr_text
    assert f"tail={scene_data.tail!r}" in repr_text
    assert "has_mod=False" in repr_text


def test_koikatu_scene_repr_has_mod_for_mod_scene(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_mod.png")
    assert "has_mod=True" in repr(scene_data)


def test_koikatu_scene_original_filename_for_bytes_input(data_dir):
    with open(data_dir / "kk_scene_simple.png", "rb") as f:
        raw_data = f.read()
    scene_data = KoikatuSceneData.load(raw_data)
    assert scene_data.original_filename is None


def count_types_recursive(objects):
    """Recursively count all objects by type including nested children"""
    type_counts = {}
    for obj in objects.values():
        obj_type = obj["type"]
        type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
        data = obj.get("data", {})
        if "child" in data and data["child"]:
            children = data["child"]
            if isinstance(children, list):
                child_dict = {i: c for i, c in enumerate(children)}
                child_counts = count_types_recursive(child_dict)
                for t, count in child_counts.items():
                    type_counts[t] = type_counts.get(t, 0) + count
    return type_counts


def test_load_kk_scene(data_dir):
    """Test loading kk_scene.png"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene.png")
    assert scene_data.version == "1.0.4.2"

    type_counts = count_types_recursive(scene_data.objects)
    assert type_counts.get(0, 0) == 1
    assert type_counts.get(1, 0) == 169
    assert type_counts.get(3, 0) == 19


def test_load_kk_scene_mod(data_dir):
    """Test loading kk_scene_mod.png"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_mod.png")
    assert scene_data.version == "1.1.2.1"

    type_counts = count_types_recursive(scene_data.objects)
    assert type_counts.get(0, 0) == 1
    assert type_counts.get(1, 0) == 201
    assert type_counts.get(2, 0) == 1
    assert type_counts.get(3, 0) == 202


def test_load_kks_scene(data_dir):
    """Test loading kks_scene.png (Koikatsu Sunshine)"""
    scene_data = KoikatuSceneData.load(data_dir / "kks_scene.png")
    assert scene_data.version == "1.1.2.1"

    type_counts = count_types_recursive(scene_data.objects)
    assert type_counts.get(2, 0) == 1
    assert type_counts.get(3, 0) == 1


def test_count_object_types_koikatu_scene(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene.png")
    assert scene_data.count_object_types() == {"Folder": 19, "Item": 169, "Character": 1}


def test_count_object_types_koikatu_mod_scene(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_mod.png")
    assert scene_data.count_object_types() == {"Folder": 202, "Item": 202, "Character": 1, "Light": 1}


def test_count_object_types_kks_scene(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kks_scene.png")
    assert scene_data.count_object_types() == {"Light": 1, "Folder": 1, "Item": 3, "Character": 1}


def test_walk_filter_object_type_koikatu(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene.png")
    chars = list(scene_data.walk(object_type=KoikatuSceneData.CHARACTER))
    assert len(chars) == scene_data.count_object_types()["Character"]
    assert all(obj["type"] == KoikatuSceneData.CHARACTER for _, obj in chars)


def test_walk_filter_object_type_koikatu_with_depth(data_dir):
    scene_data = KoikatuSceneData.load(data_dir / "kks_scene.png")
    lights = list(scene_data.walk(include_depth=True, object_type=KoikatuSceneData.LIGHT))
    assert len(lights) == scene_data.count_object_types()["Light"]
    assert all(obj["type"] == KoikatuSceneData.LIGHT for _, obj, _ in lights)


def test_scene_to_dict(data_dir):
    """Test converting a scene to a dictionary"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_simple.png")
    scene_dict = scene_data.to_dict()

    assert "version" in scene_dict
    assert "map" in scene_dict
    assert "objectCount" in scene_dict
    assert scene_dict["objectCount"] == len(scene_data.objects)


def count_all_objects(objects):
    """Recursively count all objects including nested children"""
    count = len(objects)
    for obj in objects.values():
        data = obj.get("data", {})
        if "child" in data:
            child_data = data["child"]
            if isinstance(child_data, dict):
                for child_list in child_data.values():
                    count += count_all_objects({i: obj for i, obj in enumerate(child_list)})
            elif isinstance(child_data, list):
                count += count_all_objects({i: obj for i, obj in enumerate(child_data)})
        if "route" in data and isinstance(data["route"], list):
            count += len(data["route"])
        if "bones" in data and isinstance(data["bones"], dict):
            count += len(data["bones"])
        if "ik_targets" in data and isinstance(data["ik_targets"], dict):
            count += len(data["ik_targets"])
    return count


def test_save_scene(data_dir):
    """Test saving a Koikatu scene file"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_simple.png")

    tmpfile = tempfile.NamedTemporaryFile()
    scene_data.save(tmpfile.name)

    scene_data2 = KoikatuSceneData.load(tmpfile.name)

    assert scene_data.map == scene_data2.map
    assert len(scene_data.objects) == len(scene_data2.objects)

    total_count_1 = count_all_objects(scene_data.objects)
    total_count_2 = count_all_objects(scene_data2.objects)
    assert total_count_1 == total_count_2, f"Total object count mismatch: {total_count_1} vs {total_count_2}"

    obj_key = list(scene_data.objects.keys())[0]
    obj_key2 = list(scene_data2.objects.keys())[0]

    assert scene_data.objects[obj_key]["type"] == scene_data2.objects[obj_key2]["type"]

    for key in scene_data.objects.keys():
        obj1 = scene_data.objects[key]
        obj2 = scene_data2.objects[key]

        assert obj1["type"] == obj2["type"], f"Object {key} type mismatch"

        data1 = obj1["data"]
        data2 = obj2["data"]

        assert data1.get("dicKey") == data2.get("dicKey"), f"Object {key} dicKey mismatch"

        for field in ["position", "rotation", "scale"]:
            if field in data1 and field in data2:
                v1 = data1[field]
                v2 = data2[field]
                for axis in ["x", "y", "z"]:
                    assert abs(v1.get(axis, 0.0) - v2.get(axis, 0.0)) < 1e-6, f"Object {key} {field}.{axis} mismatch: {v1.get(axis)} vs {v2.get(axis)}"

    assert scene_data.sunLightType == scene_data2.sunLightType
    assert scene_data.mapOption == scene_data2.mapOption
    assert scene_data.aceNo == scene_data2.aceNo
    assert abs(scene_data.aceBlend - scene_data2.aceBlend) < 1e-6


def test_save_complex_scene(data_dir):
    """Test saving a complex Koikatu scene file with multiple object types"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene.png")

    tmpfile = tempfile.NamedTemporaryFile()
    scene_data.save(tmpfile.name)

    scene_data2 = KoikatuSceneData.load(tmpfile.name)

    type_counts1 = count_types_recursive(scene_data.objects)
    type_counts2 = count_types_recursive(scene_data2.objects)
    assert type_counts1 == type_counts2


def test_save_kk_scene_mod(data_dir):
    """Test saving kk_scene_mod.png"""
    scene_data = KoikatuSceneData.load(data_dir / "kk_scene_mod.png")

    tmpfile = tempfile.NamedTemporaryFile()
    scene_data.save(tmpfile.name)

    scene_data2 = KoikatuSceneData.load(tmpfile.name)

    type_counts1 = count_types_recursive(scene_data.objects)
    type_counts2 = count_types_recursive(scene_data2.objects)
    assert type_counts1 == type_counts2


def test_save_kks_scene(data_dir):
    """Test saving kks_scene.png (Koikatsu Sunshine)"""
    scene_data = KoikatuSceneData.load(data_dir / "kks_scene.png")

    tmpfile = tempfile.NamedTemporaryFile()
    scene_data.save(tmpfile.name)

    scene_data2 = KoikatuSceneData.load(tmpfile.name)

    type_counts1 = count_types_recursive(scene_data.objects)
    type_counts2 = count_types_recursive(scene_data2.objects)
    assert type_counts1 == type_counts2


# ============================================================
# Honeycome scene tests
# ============================================================


def test_load_honeycome_scene_items(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_items.png")

    assert hasattr(scene_data, "version")
    assert hasattr(scene_data, "objects")
    assert hasattr(scene_data, "user_id")
    assert hasattr(scene_data, "data_id")
    assert hasattr(scene_data, "title")

    assert len(scene_data.objects) > 0

    has_folder = any(obj["type"] == 3 for obj in scene_data.objects.values())
    assert has_folder, "Expected at least one folder object in hc_scene_items.png"


def test_honeycome_scene_repr_fields(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_items.png")
    repr_text = repr(scene_data)

    assert f"version={scene_data.version!r}" in repr_text
    assert f"title={scene_data.title!r}" in repr_text
    assert f"objects={len(scene_data.objects)}" in repr_text


def test_honeycome_scene_original_filename_for_bytes_input(data_dir):
    with open(data_dir / "hc_scene_items.png", "rb") as f:
        raw_data = f.read()
    scene_data = HoneycomeSceneData.load(raw_data)
    assert scene_data.original_filename is None


def test_honeycome_scene_to_dict(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_items.png")
    scene_dict = scene_data.to_dict()

    assert "version" in scene_dict
    assert "user_id" in scene_dict
    assert "data_id" in scene_dict
    assert "title" in scene_dict
    assert "objectCount" in scene_dict

    assert scene_dict["objectCount"] == len(scene_data.objects)


def test_save_honeycome_scene_roundtrip(data_dir):
    scene_data_1 = HoneycomeSceneData.load(data_dir / "hc_scene_items.png")

    output_stream = io.BytesIO()
    scene_data_1.save(output_stream)

    output_stream.seek(0)
    scene_data_2 = HoneycomeSceneData.load(output_stream)

    assert scene_data_1.version == scene_data_2.version, "Version mismatch"
    assert scene_data_1.dataVersion == scene_data_2.dataVersion, "Data version mismatch"
    assert scene_data_1.user_id == scene_data_2.user_id, "User ID mismatch"
    assert scene_data_1.data_id == scene_data_2.data_id, "Data ID mismatch"
    assert scene_data_1.title == scene_data_2.title, "Title mismatch"
    assert scene_data_1.language == scene_data_2.language, "Language mismatch"
    assert len(scene_data_1.objects) == len(scene_data_2.objects), "Object count mismatch"
    assert scene_data_1.frame_filename == scene_data_2.frame_filename, "Frame filename mismatch"
    assert scene_data_1.footer_marker == scene_data_2.footer_marker, "Footer marker mismatch"
    assert scene_data_1.unknown_tail_extra is None

    assert set(scene_data_1.objects.keys()) == set(scene_data_2.objects.keys()), "Object keys mismatch"

    for key in scene_data_1.objects.keys():
        obj1 = scene_data_1.objects[key]
        obj2 = scene_data_2.objects[key]

        assert obj1["type"] == obj2["type"], f"Object {key} type mismatch"

        data1 = obj1["data"]
        data2 = obj2["data"]

        assert data1.get("dicKey") == data2.get("dicKey"), f"Object {key} dicKey mismatch"
        assert data1.get("treeState") == data2.get("treeState"), f"Object {key} treeState mismatch"
        assert data1.get("visible") == data2.get("visible"), f"Object {key} visible mismatch"

        for field in ["position", "rotation", "scale"]:
            if field in data1 and field in data2:
                v1 = data1[field]
                v2 = data2[field]
                for axis in ["x", "y", "z"]:
                    assert abs(v1.get(axis, 0.0) - v2.get(axis, 0.0)) < 1e-6, f"Object {key} {field}.{axis} mismatch"

        if obj1["type"] == 1:  # Item
            assert data1.get("group") == data2.get("group"), f"Item {key} group mismatch"
            assert data1.get("category") == data2.get("category"), f"Item {key} category mismatch"
            assert data1.get("no") == data2.get("no"), f"Item {key} no mismatch"

        elif obj1["type"] == 3:  # Folder
            assert data1.get("name") == data2.get("name"), f"Folder {key} name mismatch"
            assert len(data1.get("child", [])) == len(data2.get("child", [])), f"Folder {key} child count mismatch"


def test_save_honeycome_scene_binary_exact(data_dir):
    with open(data_dir / "hc_scene_items.png", "rb") as f:
        original_bytes = f.read()

    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_items.png")

    output_stream = io.BytesIO()
    scene_data.save(output_stream)
    saved_bytes = output_stream.getvalue()

    assert len(original_bytes) == len(saved_bytes), f"File size mismatch: {len(original_bytes)} vs {len(saved_bytes)}"
    assert original_bytes == saved_bytes, "Saved file is not byte-for-byte identical to original"


def _find_obj_by_type(scene_data, target_type, *, nested=False):
    """Find the first object with the given type. If nested, search in folder children too."""
    for key, obj in scene_data.objects.items():
        if obj["type"] == target_type:
            return key, obj
    if nested:
        for obj in scene_data.objects.values():
            if obj["type"] == 3:
                result = _find_nested_object_by_type(obj["data"], target_type)
                if result:
                    return None, result
    return None, None


def _find_nested_object_by_type(folder_data, target_type):
    for child in folder_data.get("child", []):
        if child["type"] == target_type:
            return child
        if child["type"] == 3:
            result = _find_nested_object_by_type(child["data"], target_type)
            if result:
                return result
    return None


PRESERVATION_CASES = [
    ("hc_scene_items.png", 1, True, ["group", "category", "no", "anime_pattern"], ["anime_speed"], "item"),
    ("hc_scene_items.png", 3, False, ["name"], [], "folder"),
    ("hc_scene_objects.png", 2, False, ["no"], ["intensity", "range", "outsideSpotAngle", "insideSpotAngle"], "light"),
    ("hc_scene_objects.png", 4, False, ["name", "active", "loop", "visibleLine"], [], "route"),
    ("hc_scene_objects.png", 0, True, ["dicKey", "visible"], [], "nested_char"),
    ("hc_scene_objects.png", 5, True, ["dicKey", "active"], [], "nested_camera"),
    ("hc_scene_objects.png", 1, True, ["group", "category", "no"], [], "nested_item"),
]


@pytest.mark.parametrize(
    "scene_file, obj_type, nested, exact_fields, float_fields",
    [c[:5] for c in PRESERVATION_CASES],
    ids=[c[5] for c in PRESERVATION_CASES],
)
def test_object_data_preservation(scene_file, obj_type, nested, exact_fields, float_fields, data_dir, tmp_path):
    scene_data = HoneycomeSceneData.load(data_dir / scene_file)

    key, obj = _find_obj_by_type(scene_data, obj_type, nested=nested)
    assert obj is not None, f"Expected at least one object of type {obj_type} in {scene_file}"

    out_path = tmp_path / scene_file
    scene_data.save(str(out_path))
    scene_data2 = HoneycomeSceneData.load(str(out_path))

    if nested:
        _, obj2 = _find_obj_by_type(scene_data2, obj_type, nested=True)
    else:
        obj2 = scene_data2.objects[key]

    assert obj2 is not None, f"Expected object of type {obj_type} after reload"

    data1 = obj["data"]
    data2 = obj2["data"]

    for field in exact_fields:
        assert data1[field] == data2[field], f"{field} mismatch"

    for field in float_fields:
        assert abs(data1[field] - data2[field]) < 1e-6, f"{field} mismatch"

    if obj_type == 1 and not nested:
        assert len(data1["colors"]) == len(data2["colors"])
        for i, (c1, c2) in enumerate(zip(data1["colors"], data2["colors"])):
            if c1 is None:
                assert c2 is None, f"Color {i} mismatch"
            else:
                assert c1 == c2, f"Color {i} mismatch"

        assert len(data1["patterns"]) == len(data2["patterns"])
        for i, (p1, p2) in enumerate(zip(data1["patterns"], data2["patterns"])):
            assert p1["key"] == p2["key"], f"Pattern {i} key mismatch"
            assert p1["clamp"] == p2["clamp"], f"Pattern {i} clamp mismatch"
            assert p1["uv"] == p2["uv"], f"Pattern {i} uv mismatch"

    if obj_type == 2:
        assert data1["color"] == data2["color"], "Light color mismatch"
        assert data1["shadow"] == data2["shadow"], "Light shadow mismatch"

    if obj_type == 3:
        assert len(data1.get("child", [])) == len(data2.get("child", []))

    if obj_type == 4:
        assert len(data1["route_points"]) == len(data2["route_points"])
        for i, (p1, p2) in enumerate(zip(data1["route_points"], data2["route_points"])):
            for field in ["position", "rotation"]:
                if field in p1 and field in p2:
                    for axis in ["x", "y", "z"]:
                        assert abs(p1[field].get(axis, 0.0) - p2[field].get(axis, 0.0)) < 1e-6
            assert abs(p1.get("speed", 0.0) - p2.get("speed", 0.0)) < 1e-6

    if obj_type == 0 and nested:
        assert "character" in data1
        assert "character" in data2


def test_load_honeycome_scene_objects(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_objects.png")

    assert hasattr(scene_data, "version")
    assert hasattr(scene_data, "objects")
    assert len(scene_data.objects) == 8

    type_counts = {}
    for obj in scene_data.objects.values():
        t = obj["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    assert type_counts.get(2, 0) == 2, "Expected 2 light objects"
    assert type_counts.get(3, 0) == 5, "Expected 5 folder objects"
    assert type_counts.get(4, 0) == 1, "Expected 1 route object"


def test_count_object_types_honeycome_scene_items(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_items.png")
    assert scene_data.count_object_types() == {"Folder": 76, "Item": 150}


def test_count_object_types_honeycome_scene_objects(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_objects.png")
    assert scene_data.count_object_types() == {
        "Folder": 8,
        "Item": 1,
        "Character": 1,
        "Light": 3,
        "Camera": 1,
        "Route": 1,
    }


def test_walk_filter_object_type_honeycome(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_objects.png")
    folders = list(scene_data.walk(object_type=HoneycomeSceneData.FOLDER))
    assert len(folders) == scene_data.count_object_types()["Folder"]
    assert all(obj["type"] == HoneycomeSceneData.FOLDER for _, obj in folders)


def test_walk_filter_object_type_honeycome_with_depth(data_dir):
    scene_data = HoneycomeSceneData.load(data_dir / "hc_scene_objects.png")
    cameras = list(scene_data.walk(include_depth=True, object_type=HoneycomeSceneData.CAMERA))
    assert len(cameras) == scene_data.count_object_types()["Camera"]
    assert all(obj["type"] == HoneycomeSceneData.CAMERA for _, obj, _ in cameras)


# ============================================================
# Honeycome scene encrypted block tests (require crypto keys)
# ============================================================

HC_SCENE_FILES = ["hc_scene_items.png", "hc_scene_objects.png"]


@pytest.mark.parametrize("scene_file", HC_SCENE_FILES)
def test_load_honeycome_scene_decrypted_blocks(scene_file, data_dir, hc_crypto):
    key, iv = hc_crypto
    scene = HoneycomeSceneData.load(data_dir / scene_file, decryption_key=key, decryption_iv=iv)

    assert scene.scene_summary is not None
    assert "chara_num" in scene.scene_summary
    assert "item_num" in scene.scene_summary
    assert "map" in scene.scene_summary
    assert isinstance(scene.scene_summary["chara_num"], int)

    assert scene.map_info is not None
    assert "no" in scene.map_info
    assert "option" in scene.map_info
    assert "light" in scene.map_info

    assert scene.post_processing is not None
    for pp_key in ["background", "bloom", "fog", "vignette", "depth_of_field"]:
        assert pp_key in scene.post_processing

    assert scene.camera is not None
    assert "pos" in scene.camera
    assert "rotate" in scene.camera
    assert "distance" in scene.camera
    assert "parse" in scene.camera

    assert scene.camera_presets is not None
    assert isinstance(scene.camera_presets, list)

    assert scene.chara_light is not None
    assert "color" in scene.chara_light
    assert "intensity" in scene.chara_light

    assert scene.key_light is not None
    assert "enable" in scene.key_light
    assert "shadow" in scene.key_light

    assert scene.bgm is not None
    assert "play" in scene.bgm
    assert "no" in scene.bgm

    assert scene.env_sound is not None
    assert scene.outside_sound is not None
    assert scene.background is not None
    assert scene.common_info is not None
    assert "item_lamp" in scene.common_info


@pytest.mark.parametrize("scene_file", HC_SCENE_FILES)
def test_load_honeycome_scene_without_keys_leaves_blocks_none(scene_file, data_dir):
    scene = HoneycomeSceneData.load(data_dir / scene_file)

    assert scene.scene_summary is None
    assert scene.map_info is None
    assert scene.post_processing is None
    assert scene.camera is None
    assert scene.common_info is None


@pytest.mark.parametrize("scene_file", HC_SCENE_FILES)
def test_save_honeycome_scene_encrypted_roundtrip(scene_file, data_dir, hc_crypto):
    key, iv = hc_crypto
    scene_1 = HoneycomeSceneData.load(data_dir / scene_file, decryption_key=key, decryption_iv=iv)

    buf = io.BytesIO()
    scene_1.save(buf)

    buf.seek(0)
    scene_2 = HoneycomeSceneData.load(buf, decryption_key=key, decryption_iv=iv)

    assert scene_1.scene_summary == scene_2.scene_summary
    assert scene_1.map_info == scene_2.map_info
    assert scene_1.camera == scene_2.camera
    assert scene_1.bgm == scene_2.bgm
    assert scene_1.env_sound == scene_2.env_sound
    assert scene_1.outside_sound == scene_2.outside_sound
    assert scene_1.background == scene_2.background
    assert scene_1.common_info == scene_2.common_info
    assert scene_1.key_light == scene_2.key_light

    assert len(scene_1.objects) == len(scene_2.objects)
    for k in scene_1.objects:
        assert scene_1.objects[k]["type"] == scene_2.objects[k]["type"]


@pytest.mark.parametrize("scene_file", HC_SCENE_FILES)
def test_save_honeycome_scene_encrypted_to_dict(scene_file, data_dir, hc_crypto):
    key, iv = hc_crypto
    scene = HoneycomeSceneData.load(data_dir / scene_file, decryption_key=key, decryption_iv=iv)
    d = scene.to_dict()

    assert d["scene_summary"] is not None
    assert d["scene_summary"]["chara_num"] == scene.scene_summary["chara_num"]
    assert d["map_info"] == scene.map_info
    assert d["bgm"] == scene.bgm
    assert d["common_info"] == scene.common_info


# ============================================================
# EmotionCreators scene tests
# ============================================================


def test_load_emocre_scene(data_dir):
    scene = EmocreSceneData.load(data_dir / "ec_scene.png")
    assert scene.header == "【EroMakeHScene】"
    assert scene.product_no == 200
    assert len(scene.charas) > 0
    assert len(scene.maps) > 0
    assert len(scene.parts) > 0
    assert scene.node_graph is not None
    assert len(scene.node_graph.nodes) > 0


def test_save_emocre_scene(data_dir):
    with open(data_dir / "ec_scene.png", "rb") as f:
        raw_data = f.read()
    scene = EmocreSceneData.load(data_dir / "ec_scene.png")
    tmpfile = tempfile.NamedTemporaryFile()
    scene.save(tmpfile.name)
    scene2 = EmocreSceneData.load(tmpfile.name)
    assert scene.info["title"] == scene2.info["title"]
    assert raw_data == bytes(scene)
    assert bytes(scene) == bytes(scene2)
