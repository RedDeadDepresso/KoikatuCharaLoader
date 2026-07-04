"""Base class for scene object load/save helpers shared by Koikatu and Honeycome."""

import json
import struct
from typing import Any, BinaryIO, Dict

from kkloader.funcs import load_string, load_type, write_string


class SceneObjectLoaderBase:
    """Base class with shared scene object load/save methods.

    Subclasses must define _LOAD_DISPATCH and _SAVE_DISPATCH class variables,
    and override any object-type-specific load/save methods that differ.
    """

    _LOAD_DISPATCH: dict[int, str] = {}
    _SAVE_DISPATCH: dict[int, str] = {}

    @classmethod
    def _dispatch_load(cls, data_stream: BinaryIO, obj_type: int, obj_info: Dict[str, Any], version: str | None = None) -> None:
        method_name = cls._LOAD_DISPATCH.get(obj_type)
        if method_name is None:
            raise ValueError(f"Unknown object type: {obj_type}")
        method = getattr(cls, method_name)
        method(data_stream, obj_info, version)

    @classmethod
    def _dispatch_save(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        obj_type = obj_info.get("type", -1)
        method_name = cls._SAVE_DISPATCH.get(obj_type)
        if method_name is None:
            raise ValueError(f"Unknown object type: {obj_type}")
        method = getattr(cls, method_name)
        method(data_stream, obj_info, version)

    @staticmethod
    def _load_vector3(data_stream: BinaryIO) -> Dict[str, float]:
        return {"x": load_type(data_stream, "f"), "y": load_type(data_stream, "f"), "z": load_type(data_stream, "f")}

    @staticmethod
    def _save_vector3(data_stream: BinaryIO, vector3: Dict[str, float]) -> None:
        data_stream.write(struct.pack("f", vector3["x"]))
        data_stream.write(struct.pack("f", vector3["y"]))
        data_stream.write(struct.pack("f", vector3["z"]))

    @staticmethod
    def _load_color_rgba(data_stream: BinaryIO) -> Dict[str, float]:
        return {"r": load_type(data_stream, "f"), "g": load_type(data_stream, "f"), "b": load_type(data_stream, "f"), "a": load_type(data_stream, "f")}

    @staticmethod
    def _save_color_rgba(data_stream: BinaryIO, color: Dict[str, float]) -> None:
        data_stream.write(struct.pack("f", color["r"]))
        data_stream.write(struct.pack("f", color["g"]))
        data_stream.write(struct.pack("f", color["b"]))
        data_stream.write(struct.pack("f", color["a"]))

    @staticmethod
    def parse_color_json(json_str: str) -> Dict[str, float]:
        color_data = json.loads(json_str)
        return {"r": color_data.get("r", 0), "g": color_data.get("g", 0), "b": color_data.get("b", 0), "a": color_data.get("a", 1.0)}

    @staticmethod
    def _save_color_json(data_stream: BinaryIO, color: Dict[str, float]) -> None:
        color_bytes = json.dumps(color, separators=(",", ":")).encode("utf-8")
        write_string(data_stream, color_bytes)

    @staticmethod
    def _load_bool_array(data_stream: BinaryIO, count: int) -> list[bool]:
        return [bool(load_type(data_stream, "b")) for _ in range(count)]

    @classmethod
    def _load_object_info_base(cls, data_stream: BinaryIO) -> Dict[str, Any]:
        return {
            "dicKey": load_type(data_stream, "i"),
            "position": cls._load_vector3(data_stream),
            "rotation": cls._load_vector3(data_stream),
            "scale": cls._load_vector3(data_stream),
            "treeState": load_type(data_stream, "i"),
            "visible": bool(load_type(data_stream, "b")),
        }

    @classmethod
    def _save_object_info_base(cls, data_stream: BinaryIO, data: Dict[str, Any]) -> None:
        data_stream.write(struct.pack("i", data["dicKey"]))
        cls._save_vector3(data_stream, data["position"])
        cls._save_vector3(data_stream, data["rotation"])
        cls._save_vector3(data_stream, data["scale"])
        data_stream.write(struct.pack("i", data["treeState"]))
        data_stream.write(struct.pack("b", int(data["visible"])))

    @classmethod
    def load_bone_info(cls, data_stream: BinaryIO) -> Dict[str, Any]:
        bone_data = {}
        bone_data["dicKey"] = load_type(data_stream, "i")
        bone_data["changeAmount"] = {"position": cls._load_vector3(data_stream), "rotation": cls._load_vector3(data_stream), "scale": cls._load_vector3(data_stream)}
        return bone_data

    @classmethod
    def save_bone_info(cls, data_stream: BinaryIO, bone_data: Dict[str, Any]) -> None:
        data_stream.write(struct.pack("i", bone_data["dicKey"]))
        change_amount = bone_data["changeAmount"]
        cls._save_vector3(data_stream, change_amount["position"])
        cls._save_vector3(data_stream, change_amount["rotation"])
        cls._save_vector3(data_stream, change_amount["scale"])

    @classmethod
    def _load_route_point_aid_info(cls, data_stream: BinaryIO) -> Dict[str, Any]:
        aid_info = {}
        aid_info["dicKey"] = load_type(data_stream, "i")
        aid_info["changeAmount"] = {"position": cls._load_vector3(data_stream), "rotation": cls._load_vector3(data_stream), "scale": cls._load_vector3(data_stream)}
        aid_info["isInit"] = bool(load_type(data_stream, "b"))
        return aid_info

    @classmethod
    def _save_route_point_aid_info(cls, data_stream: BinaryIO, aid_info: Dict[str, Any]) -> None:
        data_stream.write(struct.pack("i", aid_info["dicKey"]))
        change_amount = aid_info["changeAmount"]
        cls._save_vector3(data_stream, change_amount["position"])
        cls._save_vector3(data_stream, change_amount["rotation"])
        cls._save_vector3(data_stream, change_amount["scale"])
        data_stream.write(struct.pack("b", int(aid_info["isInit"])))

    @classmethod
    def load_folder_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        name_bytes = load_string(data_stream)
        data["name"] = name_bytes.decode("utf-8")
        data["child"] = cls.load_child_objects(data_stream, version)
        obj_info["data"] = data

    @classmethod
    def save_folder_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)
        name = data["name"]
        name_bytes = name.encode("utf-8") if isinstance(name, str) else name
        write_string(data_stream, name_bytes)
        child_list = data["child"]
        data_stream.write(struct.pack("i", len(child_list)))
        for child in child_list:
            cls.save_child_objects(data_stream, child, version)

    @classmethod
    def load_camera_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = cls._load_object_info_base(data_stream)
        name_bytes = load_string(data_stream)
        data["name"] = name_bytes.decode("utf-8")
        data["active"] = bool(load_type(data_stream, "b"))
        obj_info["data"] = data

    @classmethod
    def save_camera_info(cls, data_stream: BinaryIO, obj_info: Dict[str, Any], version: str | None = None) -> None:
        data = obj_info["data"]
        cls._save_object_info_base(data_stream, data)
        name = data["name"]
        name_bytes = name.encode("utf-8") if isinstance(name, str) else name
        write_string(data_stream, name_bytes)
        data_stream.write(struct.pack("b", int(data["active"])))

    @classmethod
    def load_child_objects(cls, data_stream: BinaryIO, version: str | None = None) -> list[Dict[str, Any]]:
        child_list = []
        count = load_type(data_stream, "i")
        for obj_idx in range(count):
            obj_type = load_type(data_stream, "i")
            obj_info = {"type": obj_type, "data": {}}
            cls._dispatch_load(data_stream, obj_type, obj_info, version)
            child_list.append(obj_info)
        return child_list

    @classmethod
    def save_child_objects(cls, data_stream: BinaryIO, child_data: Dict[str, Any], version: str | None = None) -> None:
        obj_type = child_data.get("type", -1)
        data_stream.write(struct.pack("i", obj_type))
        cls._dispatch_save(data_stream, child_data, version)
