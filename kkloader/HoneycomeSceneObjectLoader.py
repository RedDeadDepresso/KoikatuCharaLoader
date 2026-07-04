"""Honeycome scene object load/save helpers."""

import io
import json
import struct
from typing import Any, BinaryIO, Dict, Tuple, Type

from kkloader.AicomiCharaData import AicomiCharaData
from kkloader.funcs import get_png, has_png_magic, load_length, load_string, load_type, write_string
from kkloader.HoneycomeCharaData import HoneycomeCharaData
from kkloader.SceneObjectLoaderBase import SceneObjectLoaderBase
from kkloader.SummerVacationCharaData import SummerVacationCharaData


class HoneycomeSceneObjectLoader(SceneObjectLoaderBase):
    """Honeycome-specific scene object loader/saver.

    Extends SceneObjectLoaderBase with Honeycome-specific object types
    and character data dispatching.
    """

    _LOAD_DISPATCH = {
        0: "load_char_info",
        1: "load_item_info",
        2: "load_light_info",
        3: "load_folder_info",
        4: "load_route_info",
        5: "load_camera_info",
    }

    _SAVE_DISPATCH = {
        0: "save_char_info",
        1: "save_item_info",
        2: "save_light_info",
        3: "save_folder_info",
        4: "save_route_info",
        5: "save_camera_info",
    }

    _CHARA_DATA_DISPATCH = {
        b"\xe3\x80\x90HCPChara\xe3\x80\x91": HoneycomeCharaData,
        b"\xe3\x80\x90HCChara\xe3\x80\x91": HoneycomeCharaData,
        b"\xe3\x80\x90SVChara\xe3\x80\x91": SummerVacationCharaData,
        b"\xe3\x80\x90ACChara\xe3\x80\x91": AicomiCharaData,
        b"\xe3\x80\x90DCChara\xe3\x80\x91": HoneycomeCharaData,
    }

    @staticmethod
    def _get_chara_data_class(data_stream: BinaryIO) -> Tuple[Type, bool]:
        start_pos = data_stream.tell()
        has_png = has_png_magic(data_stream)
        if has_png:
            get_png(data_stream)
        _product_no = load_type(data_stream, "i")
        header = load_length(data_stream, "b")
        data_stream.seek(start_pos)
        chara_class = HoneycomeSceneObjectLoader._CHARA_DATA_DISPATCH.get(header)
        if chara_class is None:
            raise ValueError(f"Unknown character header: {header}")
        return chara_class, has_png

    @staticmethod
    def load_pattern_info(data_stream: BinaryIO) -> Dict[str, Any]:
        pattern_data = {}
        pattern_data["key"] = load_type(data_stream, "i")
        pattern_data["filepath"] = load_string(data_stream).decode("utf-8")
        pattern_data["clamp"] = bool(load_type(data_stream, "b"))
        uv_json = load_string(data_stream).decode("utf-8")
        pattern_data["uv"] = json.loads(uv_json)
        pattern_data["rot"] = load_type(data_stream, "f")
        return pattern_data

    @staticmethod
    def save_pattern_info(data_stream: BinaryIO, pattern_data: Dict[str, Any]) -> None:
        data_stream.write(struct.pack("i", pattern_data["key"]))
        write_string(data_stream, pattern_data["filepath"].encode("utf-8"))
        data_stream.write(struct.pack("b", int(pattern_data["clamp"])))
        write_string(data_stream, json.dumps(pattern_data["uv"], separators=(",", ":")).encode("utf-8"))
        data_stream.write(struct.pack("f", pattern_data["rot"]))

    @classmethod
    def _load_route_point_info(cls, data_stream: BinaryIO, version: str | None = None) -> Dict[str, Any]:
        route_point = {}
        route_point["dicKey"] = load_type(data_stream, "i")
        route_point["changeAmount"] = {
            "position": cls._load_vector3(data_stream),
            "rotation": cls._load_vector3(data_stream),
            "scale": cls._load_vector3(data_stream),
        }
        route_point["speed"] = load_type(data_stream, "f")
        route_point["easeType"] = load_type(data_stream, "i")
        route_point["connection"] = load_type(data_stream, "i")
        route_point["aidInfo"] = cls._load_route_point_aid_info(data_stream)
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
        data_stream.write(struct.pack("i", route_point["connection"]))
        cls._save_route_point_aid_info(data_stream, route_point["aidInfo"])
        data_stream.write(struct.pack("b", int(route_point["link"])))

    @classmethod
    def load_char_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        data["sex"] = load_type(data_stream, "i")

        try:
            chara_class, has_png = cls._get_chara_data_class(data_stream)
            chara_data = chara_class.load(data_stream, contains_png=has_png)
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
        data["anime_info"] = {
            "title": load_type(data_stream, "i"),
            "group": load_type(data_stream, "i"),
            "category": load_type(data_stream, "i"),
            "no": load_type(data_stream, "i"),
        }
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

        data["unknown"] = data_stream.read(14)

        data["enable_ik"] = bool(load_type(data_stream, "b"))
        data["active_ik"] = cls._load_bool_array(data_stream, 5)
        data["enable_fk"] = bool(load_type(data_stream, "b"))
        data["active_fk"] = cls._load_bool_array(data_stream, 7)

        data["expression"] = cls._load_bool_array(data_stream, 9)

        data["anime_speed"] = load_type(data_stream, "f")
        data["anime_pattern"] = load_type(data_stream, "f")
        data["anime_option_visible"] = bool(load_type(data_stream, "b"))
        data["is_anime_force_loop"] = bool(load_type(data_stream, "b"))

        vc_stream = io.BytesIO(data_stream.read(load_type(data_stream, "i")))
        data["voiceCtrl"] = {"list": [], "repeat": None}
        data["voiceCtrl"]["unknown"] = load_type(vc_stream, "b")
        for _ in range(load_type(vc_stream, "i")):
            voice_info = {"group": load_type(vc_stream, "i"), "category": load_type(vc_stream, "i"), "no": load_type(vc_stream, "i")}
            data["voiceCtrl"]["list"].append(voice_info)
        data["voiceCtrl"]["repeat"] = load_type(vc_stream, "i")

        data["visible_son"] = bool(load_type(data_stream, "b"))
        data["son_length"] = load_type(data_stream, "f")
        data["visible_simple"] = bool(load_type(data_stream, "b"))

        simple_color_json = load_length(data_stream, "b").decode("utf-8")
        data["simple_color"] = cls.parse_color_json(simple_color_json)

        data["anime_option_param"] = [load_type(data_stream, "f"), load_type(data_stream, "f"), load_type(data_stream, "f")]

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

        data["title"] = load_type(data_stream, "i")
        data["group"] = load_type(data_stream, "i")
        data["category"] = load_type(data_stream, "i")
        data["no"] = load_type(data_stream, "i")
        data["anime_pattern"] = load_type(data_stream, "i")
        data["anime_speed"] = load_type(data_stream, "f")

        data["colors"] = []
        for _ in range(8):
            color_bytes = load_string(data_stream)
            if len(color_bytes) > 0:
                data["colors"].append(json.loads(color_bytes.decode("utf-8")))
            else:
                data["colors"].append(None)

        data["shadow_type"] = load_type(data_stream, "i")
        data["shadow_switch"] = bool(load_type(data_stream, "b"))
        data["shadow_strength"] = load_type(data_stream, "f")

        data["patterns"] = []
        for _ in range(3):
            data["patterns"].append(cls.load_pattern_info(data_stream))

        data["alpha"] = load_type(data_stream, "f")

        line_color_json = load_string(data_stream).decode("utf-8")
        data["line_color"] = json.loads(line_color_json)
        data["line_width"] = load_type(data_stream, "f")

        emission_color_json = load_string(data_stream).decode("utf-8")
        data["emission_color"] = json.loads(emission_color_json)
        data["emission_power"] = load_type(data_stream, "f")
        data["light_cancel"] = load_type(data_stream, "f")

        data["panel"] = cls.load_pattern_info(data_stream)

        data["enable_fk"] = bool(load_type(data_stream, "b"))
        bones_count = load_type(data_stream, "i")
        data["bones"] = {}
        for _ in range(bones_count):
            bone_key = load_string(data_stream).decode("utf-8")
            data["bones"][bone_key] = cls.load_bone_info(data_stream)

        data["enable_dynamic_bone"] = bool(load_type(data_stream, "b"))
        data["anime_normalized_time"] = load_type(data_stream, "f")
        data["child"] = cls.load_child_objects(data_stream, version)
        obj_info["data"] = data

    @classmethod
    def load_light_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        data["no"] = load_type(data_stream, "i")
        data["lightSwitch"] = bool(load_type(data_stream, "b"))
        data["displayTarget"] = bool(load_type(data_stream, "b"))
        color_bytes = load_string(data_stream)
        data["color"] = cls.parse_color_json(color_bytes.decode("utf-8"))
        data["intensity"] = load_type(data_stream, "f")
        data["range"] = load_type(data_stream, "f")
        data["outsideSpotAngle"] = load_type(data_stream, "f")
        data["insideSpotAngle"] = load_type(data_stream, "f")
        data["shadow"] = bool(load_type(data_stream, "b"))
        data["shadowStrength"] = load_type(data_stream, "f")
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

        data["active"] = bool(load_type(data_stream, "b"))
        data["loop"] = bool(load_type(data_stream, "b"))
        data["visibleLine"] = bool(load_type(data_stream, "b"))
        data["orient"] = load_type(data_stream, "i")
        color_json = load_string(data_stream).decode("utf-8")
        data["color"] = json.loads(color_json)
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
        data_stream.write(struct.pack("i", anime_info["title"]))
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

        data_stream.write(data["unknown"])

        data_stream.write(struct.pack("b", int(data["enable_ik"])))
        active_ik = data["active_ik"]
        for i in range(5):
            data_stream.write(struct.pack("b", int(active_ik[i])))

        data_stream.write(struct.pack("b", int(data["enable_fk"])))
        active_fk = data["active_fk"]
        for i in range(7):
            data_stream.write(struct.pack("b", int(active_fk[i])))

        expression = data["expression"]
        for i in range(9):
            data_stream.write(struct.pack("b", int(expression[i])))

        data_stream.write(struct.pack("f", data["anime_speed"]))
        data_stream.write(struct.pack("f", data["anime_pattern"]))
        data_stream.write(struct.pack("b", int(data["anime_option_visible"])))
        data_stream.write(struct.pack("b", int(data["is_anime_force_loop"])))

        vc_buf = io.BytesIO()
        vc_buf.write(struct.pack("b", int(data["voiceCtrl"]["unknown"])))
        vc_list = data["voiceCtrl"]["list"]
        vc_buf.write(struct.pack("i", len(vc_list)))
        for voice_info in vc_list:
            vc_buf.write(struct.pack("i", voice_info["group"]))
            vc_buf.write(struct.pack("i", voice_info["category"]))
            vc_buf.write(struct.pack("i", voice_info["no"]))
        vc_buf.write(struct.pack("i", data["voiceCtrl"]["repeat"]))
        vc_bytes = vc_buf.getvalue()
        data_stream.write(struct.pack("i", len(vc_bytes)))
        data_stream.write(vc_bytes)

        data_stream.write(struct.pack("b", int(data["visible_son"])))
        data_stream.write(struct.pack("f", data["son_length"]))
        data_stream.write(struct.pack("b", int(data["visible_simple"])))

        simple_color_bytes = json.dumps(data["simple_color"], separators=(",", ":")).encode("utf-8")
        data_stream.write(struct.pack("b", len(simple_color_bytes)))
        data_stream.write(simple_color_bytes)

        anime_option_param = data["anime_option_param"]
        for i in range(3):
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

        data_stream.write(struct.pack("i", data["title"]))
        data_stream.write(struct.pack("i", data["group"]))
        data_stream.write(struct.pack("i", data["category"]))
        data_stream.write(struct.pack("i", data["no"]))
        data_stream.write(struct.pack("i", data["anime_pattern"]))
        data_stream.write(struct.pack("f", data["anime_speed"]))

        for i in range(8):
            color = data["colors"][i] if i < len(data["colors"]) and data["colors"][i] is not None else {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}
            write_string(data_stream, json.dumps(color, separators=(",", ":")).encode("utf-8"))

        data_stream.write(struct.pack("i", data["shadow_type"]))
        data_stream.write(struct.pack("b", int(data["shadow_switch"])))
        data_stream.write(struct.pack("f", data["shadow_strength"]))

        for pattern in data["patterns"]:
            cls.save_pattern_info(data_stream, pattern)

        data_stream.write(struct.pack("f", data["alpha"]))

        write_string(data_stream, json.dumps(data["line_color"], separators=(",", ":")).encode("utf-8"))
        data_stream.write(struct.pack("f", data["line_width"]))

        write_string(data_stream, json.dumps(data["emission_color"], separators=(",", ":")).encode("utf-8"))
        data_stream.write(struct.pack("f", data["emission_power"]))
        data_stream.write(struct.pack("f", data["light_cancel"]))

        cls.save_pattern_info(data_stream, data["panel"])

        data_stream.write(struct.pack("b", int(data["enable_fk"])))
        data_stream.write(struct.pack("i", len(data["bones"])))
        for bone_key, bone_data in data["bones"].items():
            write_string(data_stream, bone_key.encode("utf-8"))
            cls.save_bone_info(data_stream, bone_data)

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
        data_stream.write(struct.pack("b", int(data["lightSwitch"])))
        data_stream.write(struct.pack("b", int(data["displayTarget"])))
        cls._save_color_json(data_stream, data["color"])
        data_stream.write(struct.pack("f", data["intensity"]))
        data_stream.write(struct.pack("f", data["range"]))
        data_stream.write(struct.pack("f", data["outsideSpotAngle"]))
        data_stream.write(struct.pack("f", data["insideSpotAngle"]))
        data_stream.write(struct.pack("b", int(data["shadow"])))
        data_stream.write(struct.pack("f", data["shadowStrength"]))

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

        data_stream.write(struct.pack("b", int(data["active"])))
        data_stream.write(struct.pack("b", int(data["loop"])))
        data_stream.write(struct.pack("b", int(data["visibleLine"])))
        data_stream.write(struct.pack("i", data["orient"]))
        cls._save_color_json(data_stream, data["color"])
