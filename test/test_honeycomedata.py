import io

from kkloader import HoneycomeSceneData

import pytest


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
    assert f"user_id={scene_data.user_id!r}" in repr_text
    assert f"data_id={scene_data.data_id!r}" in repr_text
    assert f"original_filename={str((data_dir / 'hc_scene_items.png').resolve())!r}" in repr_text
    assert f"footer_marker={scene_data.footer_marker!r}" in repr_text


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
    assert scene_data_1.unknown_1 == scene_data_2.unknown_1, "Unknown 1 mismatch"
    assert scene_data_1.unknown_2 == scene_data_2.unknown_2, "Unknown 2 mismatch"
    assert len(scene_data_1.objects) == len(scene_data_2.objects), "Object count mismatch"
    assert scene_data_1.unknown_tail == scene_data_2.unknown_tail, "Unknown tail mismatch"
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


ITEM_FIELDS = ["group", "category", "no", "anime_pattern"]
ITEM_FLOAT_FIELDS = ["anime_speed"]

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


# ============================================================
# Tests for hc_scene_objects.png
# ============================================================


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
