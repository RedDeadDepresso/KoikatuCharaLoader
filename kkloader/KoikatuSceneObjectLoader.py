"""Koikatu scene object load/save helpers."""

import json
import struct
from typing import Any, BinaryIO, Dict

from kkloader.funcs import compare_versions, load_length, load_string, load_type, write_string
from kkloader.KoikatuCharaData import KoikatuCharaData
from kkloader.SceneObjectLoaderBase import SceneObjectLoaderBase


class KoikatuSceneObjectLoader(SceneObjectLoaderBase):
    """Koikatu-specific scene object loader/saver.

    Extends SceneObjectLoaderBase with Koikatu-specific object types and
    version-gated field handling.
    """

    _LOAD_DISPATCH = {
        0: "load_char_info",
        1: "load_item_info",
        2: "load_light_info",
        3: "load_folder_info",
        4: "load_route_info",
        5: "load_camera_info",
        7: "load_text_info",
    }

    _SAVE_DISPATCH = {
        0: "save_char_info",
        1: "save_item_info",
        2: "save_light_info",
        3: "save_folder_info",
        4: "save_route_info",
        5: "save_camera_info",
        7: "save_text_info",
    }

    @classmethod
    def _load_light_info_base(cls, data_stream: BinaryIO) -> Dict[str, Any]:
        color_json = load_string(data_stream).decode("utf-8")
        return {
            "color": cls.parse_color_json(color_json),
            "intensity": load_type(data_stream, "f"),
            "rot": [load_type(data_stream, "f"), load_type(data_stream, "f")],
            "shadow": bool(load_type(data_stream, "b")),
        }

    @staticmethod
    def _save_light_info_base(data_stream: BinaryIO, light_data: Dict[str, Any]) -> None:
        color_bytes = json.dumps(light_data["color"], separators=(",", ":")).encode("utf-8")
        write_string(data_stream, color_bytes)
        data_stream.write(struct.pack("f", light_data["intensity"]))
        data_stream.write(struct.pack("f", light_data["rot"][0]))
        data_stream.write(struct.pack("f", light_data["rot"][1]))
        data_stream.write(struct.pack("b", int(light_data["shadow"])))

    @staticmethod
    def load_pattern_info(data_stream: BinaryIO) -> Dict[str, Any]:
        pattern_data = {}
        pattern_data["key"] = load_type(data_stream, "i")
        file_path_bytes = load_string(data_stream)
        pattern_data["file_path"] = file_path_bytes.decode("utf-8")
        pattern_data["clamp"] = bool(load_type(data_stream, "b"))
        uv_json = load_string(data_stream).decode("utf-8")
        pattern_data["uv"] = json.loads(uv_json)
        pattern_data["rot"] = load_type(data_stream, "f")
        return pattern_data

    @staticmethod
    def save_pattern_info(data_stream: BinaryIO, pattern_data: Dict[str, Any]) -> None:
        data_stream.write(struct.pack("i", pattern_data["key"]))
        write_string(data_stream, pattern_data["file_path"].encode("utf-8"))
        data_stream.write(struct.pack("b", int(pattern_data["clamp"])))
        write_string(data_stream, json.dumps(pattern_data["uv"], separators=(",", ":")).encode("utf-8"))
        data_stream.write(struct.pack("f", pattern_data["rot"]))

    @classmethod
    def _load_route_point_info(cls, data_stream: BinaryIO, version: str | None = None) -> Dict[str, Any]:
        route_point = {}
        route_point["dicKey"] = load_type(data_stream, "i")
        route_point["changeAmount"] = {"position": cls._load_vector3(data_stream), "rotation": cls._load_vector3(data_stream), "scale": cls._load_vector3(data_stream)}
        route_point["speed"] = load_type(data_stream, "f")
        route_point["easeType"] = load_type(data_stream, "i")

        if cls._compare_versions(version, "1.0.3") == 0:
            data_stream.read(1)

        if cls._compare_versions(version, "1.0.4.1") >= 0:
            route_point["connection"] = load_type(data_stream, "i")

        if cls._compare_versions(version, "1.0.4.1") >= 0:
            route_point["aidInfo"] = cls._load_route_point_aid_info(data_stream)

        if cls._compare_versions(version, "1.0.4.2") >= 0:
            route_point["link"] = bool(load_type(data_stream, "b"))

        return route_point

    @classmethod
    def _save_route_point_info(cls, data_stream: BinaryIO, route_point: Dict[str, Any], version: str | None = None) -> None:
        data_stream.write(struct.pack("i", route_point["dicKey"]))
        change_amount = route_point["changeAmount"]
        cls._save_vector3(data_stream, change_amount["position"])
        cls._save_vector3(data_stream, change_amount["rotation"])
        cls._save_vector3(data_stream, change_amount["scale"])
        data_stream.write(struct.pack("f", route_point["speed"]))
        data_stream.write(struct.pack("i", route_point["easeType"]))

        if cls._compare_versions(version, "1.0.3") == 0:
            data_stream.write(struct.pack("b", 0))

        if cls._compare_versions(version, "1.0.4.1") >= 0:
            data_stream.write(struct.pack("i", route_point["connection"]))

        if cls._compare_versions(version, "1.0.4.1") >= 0:
            cls._save_route_point_aid_info(data_stream, route_point["aidInfo"])

        if cls._compare_versions(version, "1.0.4.2") >= 0:
            data_stream.write(struct.pack("b", int(route_point["link"])))

    @classmethod
    def load_char_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)

        data["sex"] = load_type(data_stream, "i")

        try:
            chara_data = KoikatuCharaData.load(data_stream, contains_png=False)
            data["character"] = chara_data
        except Exception as e:
            stream_pos_error = data_stream.tell()
            print(f"Warning: Error reading character file data at position {stream_pos_error}: {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()
            raise RuntimeError(f"Failed to load character data: {str(e)}") from e

        bones_count = load_type(data_stream, "i")
        data["bones"] = {}
        for _ in range(bones_count):
            bone_key = load_type(data_stream, "i")
            bone_data = cls.load_bone_info(data_stream)
            data["bones"][bone_key] = bone_data

        ik_count = load_type(data_stream, "i")
        data["ik_targets"] = {}
        for _ in range(ik_count):
            ik_key = load_type(data_stream, "i")
            ik_data = cls.load_bone_info(data_stream)
            data["ik_targets"][ik_key] = ik_data

        child_count = load_type(data_stream, "i")
        data["child"] = {}
        for child_idx in range(child_count):
            child_key = load_type(data_stream, "i")
            data["child"][child_key] = cls.load_child_objects(data_stream, version)

        data["kinematic_mode"] = load_type(data_stream, "i")
        data["anime_info"] = {"group": load_type(data_stream, "i"), "category": load_type(data_stream, "i"), "no": load_type(data_stream, "i")}
        data["hand_patterns"] = [load_type(data_stream, "i"), load_type(data_stream, "i")]
        data["nipple"] = load_type(data_stream, "f")
        data["siru"] = data_stream.read(5)
        data["mouth_open"] = load_type(data_stream, "f")
        data["lip_sync"] = bool(load_type(data_stream, "b"))

        data["lookAtTarget"] = {
            "dicKey": load_type(data_stream, "i"),
            "position": cls._load_vector3(data_stream),
            "rotation": cls._load_vector3(data_stream),
            "scale": cls._load_vector3(data_stream),
        }

        data["enable_ik"] = bool(load_type(data_stream, "b"))
        data["active_ik"] = cls._load_bool_array(data_stream, 5)
        data["enable_fk"] = bool(load_type(data_stream, "b"))
        data["active_fk"] = cls._load_bool_array(data_stream, 7)

        expression_count = 8 if cls._compare_versions(version, "0.0.9") >= 0 else 4
        data["expression"] = cls._load_bool_array(data_stream, expression_count)

        data["anime_speed"] = load_type(data_stream, "f")
        data["anime_pattern"] = load_type(data_stream, "f")
        data["anime_option_visible"] = bool(load_type(data_stream, "b"))
        data["is_anime_force_loop"] = bool(load_type(data_stream, "b"))

        voice_list_count = load_type(data_stream, "i")
        data["voiceCtrl"] = {"list": [], "repeat": None}
        for _ in range(voice_list_count):
            voice_info = {"group": load_type(data_stream, "i"), "category": load_type(data_stream, "i"), "no": load_type(data_stream, "i")}
            data["voiceCtrl"]["list"].append(voice_info)
        data["voiceCtrl"]["repeat"] = load_type(data_stream, "i")

        data["visible_son"] = bool(load_type(data_stream, "b"))
        data["son_length"] = load_type(data_stream, "f")
        data["visible_simple"] = bool(load_type(data_stream, "b"))

        simple_color_json = load_length(data_stream, "b").decode("utf-8")
        try:
            data["simple_color"] = cls.parse_color_json(simple_color_json)
        except ValueError as e:
            print(f"Warning: Error parsing simple color JSON: {str(e)}")
            data["simple_color"] = {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}

        data["anime_option_param"] = [load_type(data_stream, "f"), load_type(data_stream, "f")]

        neck_data_length = load_type(data_stream, "i")
        data["neck_byte_data"] = data_stream.read(neck_data_length)
        eyes_data_length = load_type(data_stream, "i")
        data["eyes_byte_data"] = data_stream.read(eyes_data_length)
        data["anime_normalized_time"] = load_type(data_stream, "f")

        dic_access_group_count = load_type(data_stream, "i")
        data["dic_access_group"] = {}
        for _ in range(dic_access_group_count):
            key = load_type(data_stream, "i")
            value = load_type(data_stream, "i")
            data["dic_access_group"][key] = value

        dic_access_no_count = load_type(data_stream, "i")
        data["dic_access_no"] = {}
        for _ in range(dic_access_no_count):
            key = load_type(data_stream, "i")
            value = load_type(data_stream, "i")
            data["dic_access_no"][key] = value

        obj_info["data"] = data

    @classmethod
    def load_item_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)

        data["group"] = load_type(data_stream, "i")
        data["category"] = load_type(data_stream, "i")
        data["no"] = load_type(data_stream, "i")

        if cls._compare_versions(version, "1.1.1.0") >= 0:
            data["anime_pattern"] = load_type(data_stream, "i")
        else:
            data["anime_pattern"] = 0

        data["anime_speed"] = load_type(data_stream, "f")

        data["colors"] = []
        if cls._compare_versions(version, "0.0.3") >= 0:
            for _ in range(8):
                color_bytes = load_string(data_stream)
                if len(color_bytes) > 0:
                    data["colors"].append(json.loads(color_bytes.decode("utf-8")))
                else:
                    data["colors"].append(None)
        else:
            for _ in range(7):
                color_bytes = load_string(data_stream)
                if len(color_bytes) > 0:
                    data["colors"].append(json.loads(color_bytes.decode("utf-8")))
                else:
                    data["colors"].append(None)
            data["colors"].append({"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0})

        data["patterns"] = []
        for _ in range(3):
            pattern_data = cls.load_pattern_info(data_stream)
            data["patterns"].append(pattern_data)

        data["alpha"] = load_type(data_stream, "f")

        if cls._compare_versions(version, "0.0.4") >= 0:
            line_color_json = load_string(data_stream).decode("utf-8")
            data["line_color"] = json.loads(line_color_json)
            data["line_width"] = load_type(data_stream, "f")
        else:
            data["line_color"] = {"r": 128.0 / 255.0, "g": 128.0 / 255.0, "b": 128.0 / 255.0, "a": 1.0}
            data["line_width"] = 1.0

        if cls._compare_versions(version, "0.0.7") >= 0:
            emission_color_json = load_string(data_stream).decode("utf-8")
            data["emission_color"] = json.loads(emission_color_json)
            data["emission_power"] = load_type(data_stream, "f")
            data["light_cancel"] = load_type(data_stream, "f")
        else:
            data["emission_color"] = {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}
            data["emission_power"] = 0.0
            data["light_cancel"] = 0.0

        if cls._compare_versions(version, "0.0.6") >= 0:
            data["panel"] = cls.load_pattern_info(data_stream)
        else:
            data["panel"] = {"key": 0, "file_path": "", "clamp": True, "uv": {"x": 0.0, "y": 0.0, "z": 1.0, "w": 1.0}, "rot": 0.0}

        data["enable_fk"] = bool(load_type(data_stream, "b"))
        bones_count = load_type(data_stream, "i")
        data["bones"] = {}
        for _ in range(bones_count):
            bone_key = load_string(data_stream).decode("utf-8")
            bone_data = cls.load_bone_info(data_stream)
            data["bones"][bone_key] = bone_data

        if cls._compare_versions(version, "1.0.1") >= 0:
            data["enable_dynamic_bone"] = bool(load_type(data_stream, "b"))
        else:
            data["enable_dynamic_bone"] = True

        data["anime_normalized_time"] = load_type(data_stream, "f")
        data["child"] = cls.load_child_objects(data_stream, version)
        obj_info["data"] = data

    @classmethod
    def load_light_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        data["no"] = load_type(data_stream, "i")
        data["color"] = cls._load_color_rgba(data_stream)
        data["intensity"] = load_type(data_stream, "f")
        data["range"] = load_type(data_stream, "f")
        data["spotAngle"] = load_type(data_stream, "f")
        data["shadow"] = bool(load_type(data_stream, "b"))
        data["enable"] = bool(load_type(data_stream, "b"))
        data["drawTarget"] = bool(load_type(data_stream, "b"))
        obj_info["data"] = data

    @classmethod
    def load_route_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        name_bytes = load_string(data_stream)
        data["name"] = name_bytes.decode("utf-8")
        data["child"] = cls.load_child_objects(data_stream, version)

        route_points_count = load_type(data_stream, "i")
        data["route_points"] = []
        for _ in range(route_points_count):
            route_point = cls._load_route_point_info(data_stream, version)
            data["route_points"].append(route_point)

        if cls._compare_versions(version, "1.0.3") >= 0:
            data["active"] = bool(load_type(data_stream, "b"))
            data["loop"] = bool(load_type(data_stream, "b"))
            data["visibleLine"] = bool(load_type(data_stream, "b"))

        if cls._compare_versions(version, "1.0.4") >= 0:
            data["orient"] = load_type(data_stream, "i")

        if cls._compare_versions(version, "1.0.4.1") >= 0:
            color_json = load_string(data_stream).decode("utf-8")
            data["color"] = json.loads(color_json)

        obj_info["data"] = data

    @classmethod
    def load_text_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        data["id"] = load_type(data_stream, "i")
        color_json = load_string(data_stream).decode("utf-8")
        data["color"] = json.loads(color_json)
        outline_color_json = load_string(data_stream).decode("utf-8")
        data["outlineColor"] = json.loads(outline_color_json)
        data["outlineSize"] = load_type(data_stream, "f")
        text_infos_length = load_type(data_stream, "i")
        text_infos_bytes = data_stream.read(text_infos_length)
        data["textInfos_raw"] = text_infos_bytes
        obj_info["data"] = data

    @classmethod
    def save_char_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)
        data_stream.write(struct.pack("i", data["sex"]))

        chara_bytes = bytes(data["character"])
        data_stream.write(chara_bytes)

        bones = data["bones"]
        data_stream.write(struct.pack("i", len(bones)))
        for bone_key, bone_data in bones.items():
            data_stream.write(struct.pack("i", bone_key))
            cls.save_bone_info(data_stream, bone_data)

        ik_targets = data["ik_targets"]
        data_stream.write(struct.pack("i", len(ik_targets)))
        for ik_key, ik_data in ik_targets.items():
            data_stream.write(struct.pack("i", ik_key))
            cls.save_bone_info(data_stream, ik_data)

        child = data["child"]
        data_stream.write(struct.pack("i", len(child)))
        for child_key, child_list in child.items():
            data_stream.write(struct.pack("i", child_key))
            data_stream.write(struct.pack("i", len(child_list)))
            for child_obj in child_list:
                cls.save_child_objects(data_stream, child_obj, version)

        data_stream.write(struct.pack("i", data["kinematic_mode"]))

        anime_info = data["anime_info"]
        data_stream.write(struct.pack("i", anime_info["group"]))
        data_stream.write(struct.pack("i", anime_info["category"]))
        data_stream.write(struct.pack("i", anime_info["no"]))

        hand_patterns = data["hand_patterns"]
        for i in range(2):
            data_stream.write(struct.pack("i", hand_patterns[i]))

        data_stream.write(struct.pack("f", data["nipple"]))
        data_stream.write(data["siru"])
        data_stream.write(struct.pack("f", data["mouth_open"]))
        data_stream.write(struct.pack("b", int(data["lip_sync"])))

        lookAtTarget = data["lookAtTarget"]
        data_stream.write(struct.pack("i", lookAtTarget["dicKey"]))
        cls._save_vector3(data_stream, lookAtTarget["position"])
        cls._save_vector3(data_stream, lookAtTarget["rotation"])
        cls._save_vector3(data_stream, lookAtTarget["scale"])

        data_stream.write(struct.pack("b", int(data["enable_ik"])))
        active_ik = data["active_ik"]
        for i in range(5):
            data_stream.write(struct.pack("b", int(active_ik[i])))

        data_stream.write(struct.pack("b", int(data["enable_fk"])))
        active_fk = data["active_fk"]
        for i in range(7):
            data_stream.write(struct.pack("b", int(active_fk[i])))

        expression_count = 8 if cls._compare_versions(version, "0.0.9") >= 0 else 4
        expression = data["expression"]
        for i in range(expression_count):
            data_stream.write(struct.pack("b", int(expression[i])))

        data_stream.write(struct.pack("f", data["anime_speed"]))
        data_stream.write(struct.pack("f", data["anime_pattern"]))
        data_stream.write(struct.pack("b", int(data["anime_option_visible"])))
        data_stream.write(struct.pack("b", int(data["is_anime_force_loop"])))

        voiceCtrl = data["voiceCtrl"]
        voice_list = voiceCtrl["list"]
        data_stream.write(struct.pack("i", len(voice_list)))
        for voice_info in voice_list:
            data_stream.write(struct.pack("i", voice_info["group"]))
            data_stream.write(struct.pack("i", voice_info["category"]))
            data_stream.write(struct.pack("i", voice_info["no"]))
        data_stream.write(struct.pack("i", voiceCtrl["repeat"]))

        data_stream.write(struct.pack("b", int(data["visible_son"])))
        data_stream.write(struct.pack("f", data["son_length"]))
        data_stream.write(struct.pack("b", int(data["visible_simple"])))

        cls._save_color_json(data_stream, data["simple_color"])

        anime_option_param = data["anime_option_param"]
        for i in range(2):
            data_stream.write(struct.pack("f", anime_option_param[i]))

        neck_byte_data = data["neck_byte_data"]
        data_stream.write(struct.pack("i", len(neck_byte_data)))
        data_stream.write(neck_byte_data)

        eyes_byte_data = data["eyes_byte_data"]
        data_stream.write(struct.pack("i", len(eyes_byte_data)))
        data_stream.write(eyes_byte_data)

        data_stream.write(struct.pack("f", data["anime_normalized_time"]))

        dic_access_group = data["dic_access_group"]
        data_stream.write(struct.pack("i", len(dic_access_group)))
        for key, value in dic_access_group.items():
            data_stream.write(struct.pack("i", key))
            data_stream.write(struct.pack("i", value))

        dic_access_no = data["dic_access_no"]
        data_stream.write(struct.pack("i", len(dic_access_no)))
        for key, value in dic_access_no.items():
            data_stream.write(struct.pack("i", key))
            data_stream.write(struct.pack("i", value))

    @classmethod
    def save_item_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)

        data_stream.write(struct.pack("i", data["group"]))
        data_stream.write(struct.pack("i", data["category"]))
        data_stream.write(struct.pack("i", data["no"]))

        if cls._compare_versions(version, "1.1.1.0") >= 0:
            data_stream.write(struct.pack("i", data["anime_pattern"]))

        data_stream.write(struct.pack("f", data["anime_speed"]))

        num_colors = 8 if cls._compare_versions(version, "0.0.3") >= 0 else 7
        for i in range(num_colors):
            write_string(data_stream, json.dumps(data["colors"][i], separators=(",", ":")).encode("utf-8"))

        for pattern in data["patterns"]:
            cls.save_pattern_info(data_stream, pattern)

        data_stream.write(struct.pack("f", data["alpha"]))

        if cls._compare_versions(version, "0.0.4") >= 0:
            write_string(data_stream, json.dumps(data["line_color"], separators=(",", ":")).encode("utf-8"))
            data_stream.write(struct.pack("f", data["line_width"]))

        if cls._compare_versions(version, "0.0.7") >= 0:
            write_string(data_stream, json.dumps(data["emission_color"], separators=(",", ":")).encode("utf-8"))
            data_stream.write(struct.pack("f", data["emission_power"]))
            data_stream.write(struct.pack("f", data["light_cancel"]))

        if cls._compare_versions(version, "0.0.6") >= 0:
            cls.save_pattern_info(data_stream, data["panel"])

        data_stream.write(struct.pack("b", int(data["enable_fk"])))
        data_stream.write(struct.pack("i", len(data["bones"])))
        for bone_key, bone_data in data["bones"].items():
            write_string(data_stream, bone_key.encode("utf-8"))
            cls.save_bone_info(data_stream, bone_data)

        if cls._compare_versions(version, "1.0.1") >= 0:
            data_stream.write(struct.pack("b", int(data["enable_dynamic_bone"])))

        data_stream.write(struct.pack("f", data["anime_normalized_time"]))

        child_list = data["child"]
        data_stream.write(struct.pack("i", len(child_list)))
        for child in child_list:
            cls.save_child_objects(data_stream, child, version)

    @classmethod
    def save_light_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)
        data_stream.write(struct.pack("i", data["no"]))
        cls._save_color_rgba(data_stream, data["color"])
        data_stream.write(struct.pack("f", data["intensity"]))
        data_stream.write(struct.pack("f", data["range"]))
        data_stream.write(struct.pack("f", data["spotAngle"]))
        data_stream.write(struct.pack("b", int(data["shadow"])))
        data_stream.write(struct.pack("b", int(data["enable"])))
        data_stream.write(struct.pack("b", int(data["drawTarget"])))

    @classmethod
    def save_route_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)

        name = data["name"]
        name_bytes = name.encode("utf-8") if isinstance(name, str) else name
        write_string(data_stream, name_bytes)

        child_list = data["child"]
        data_stream.write(struct.pack("i", len(child_list)))
        for child in child_list:
            cls.save_child_objects(data_stream, child, version)

        route_points = data["route_points"]
        data_stream.write(struct.pack("i", len(route_points)))
        for route_point in route_points:
            cls._save_route_point_info(data_stream, route_point, version)

        if cls._compare_versions(version, "1.0.3") >= 0:
            data_stream.write(struct.pack("b", int(data["active"])))
            data_stream.write(struct.pack("b", int(data["loop"])))
            data_stream.write(struct.pack("b", int(data["visibleLine"])))

        if cls._compare_versions(version, "1.0.4") >= 0:
            data_stream.write(struct.pack("i", data["orient"]))

        if cls._compare_versions(version, "1.0.4.1") >= 0:
            cls._save_color_json(data_stream, data["color"])

    @classmethod
    def save_text_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)
        data_stream.write(struct.pack("i", data["id"]))
        cls._save_color_json(data_stream, data["color"])
        cls._save_color_json(data_stream, data["outlineColor"])
        data_stream.write(struct.pack("f", data["outlineSize"]))
        text_infos_bytes = data["textInfos_raw"]
        data_stream.write(struct.pack("i", len(text_infos_bytes)))
        data_stream.write(text_infos_bytes)

    @staticmethod
    def _compare_versions(version_str: str | None, target: str) -> int:
        if version_str is None:
            return 1
        return compare_versions(version_str, target)

    @staticmethod
    def _color_to_json(color: Dict[str, float]) -> str:
        return json.dumps({"r": color.get("r", 0.0), "g": color.get("g", 0.0), "b": color.get("b", 0.0), "a": color.get("a", 1.0)}, separators=(",", ":"))
