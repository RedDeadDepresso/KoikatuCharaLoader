"""Honeycome scene data loader and saver."""

import io
import struct
import sys
from contextlib import contextmanager
from typing import Any, Self

from kkloader.funcs import get_png, load_string, load_type, to_stream, write_string
from kkloader.HoneycomeSceneObjectLoader import HoneycomeSceneObjectLoader
from kkloader.KoikatuSceneData import SceneWalkMixin

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class HoneycomeSceneData(SceneWalkMixin):
    """Honeycome scene data loader/saver with full structured parsing.

    Encrypted blocks are decrypted, Brotli-decompressed, and MemoryPack-parsed
    into structured Python dicts. On save, the reverse pipeline is applied.

    Attributes:
        image: PNG image data.
        version: Scene version string.
        user_id / data_id / title: Metadata strings.
        objects: Dictionary of scene objects keyed by object ID.
        scene_summary: SceneSummary (CharaNum, ItemNum, Map, Titles).
        map_info: MapInfo (No, ChangeAmount, Option, Light).
        post_processing: PostProcessingInfo (13 sub-objects).
        camera: CameraSaveData (Pos, Rotate, Distance, Parse).
        camera_presets: CameraData[] (list of CameraSaveData).
        chara_light: LightInfo (Color, Intensity, Rot).
        key_light: KeyLightInfo (Enable, Color, Intensity, Shadow, ...).
        bgm: BGMCtrl (Play, Loop, No, Title).
        env_sound: ENVCtrl (Play, Loop, No, Title).
        outside_sound: OutsideSoundCtrl (Play, Loop, File).
        background: BackgroundInfo (DirectoryType, File).
        common_info: SceneCommonInfo (ItemLamp, CharaScaleLimit).
    """

    def __init__(self) -> None:
        self.image: bytes | None = None
        self.version: str | None = None
        self.dataVersion: str | None = None
        self.user_id: str | None = None
        self.data_id: str | None = None
        self.title: str | None = None
        self.language: int | None = None
        self.objects: dict[int, dict[str, Any]] = {}
        self.frame_filename: str | None = None
        self.footer_marker: str | None = None
        self.unknown_tail_extra: bytes | None = None
        self.crypto_key: bytes | None = None
        self.crypto_iv: bytes | None = None
        self.original_filename: str | None = None

        self.scene_summary: dict | None = None
        self.map_info: dict | None = None
        self.post_processing: dict | None = None
        self.camera: dict | None = None
        self.camera_presets: list[dict] | None = None
        self.chara_light: dict | None = None
        self.key_light: dict | None = None
        self.bgm: dict | None = None
        self.env_sound: dict | None = None
        self.outside_sound: dict | None = None
        self.background: dict | None = None
        self.common_info: dict | None = None

        # Raw encrypted blocks (kept for save without re-encryption)
        self._raw_summary: bytes = b""
        self._raw_blocks: list[bytes] = []

    @staticmethod
    @contextmanager
    def _temp_recursionlimit(limit: int):
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(limit)
        try:
            yield
        finally:
            sys.setrecursionlimit(old)

    @classmethod
    def load(
        cls,
        filelike: str | bytes | io.BytesIO,
        decryption_key: bytes | None = None,
        decryption_iv: bytes | None = None,
        recursion_limit: int = 5000,
    ) -> Self:
        """Load Honeycome scene data from a file or bytes."""
        hs = cls()
        hs.crypto_key = decryption_key
        hs.crypto_iv = decryption_iv
        data_stream, hs.original_filename = to_stream(filelike)

        hs.image = get_png(data_stream)

        version_str = load_string(data_stream).decode("utf-8")
        hs.user_id = load_string(data_stream).decode("utf-8")
        hs.data_id = load_string(data_stream).decode("utf-8")
        hs.title = load_string(data_stream).decode("utf-8")

        hs.language = load_type(data_stream, "i")
        raw_summary = data_stream.read(load_type(data_stream, "i"))

        hs.version = version_str
        hs.dataVersion = version_str

        obj_count = load_type(data_stream, "i")
        for _ in range(obj_count):
            key = load_type(data_stream, "i")
            obj_type = load_type(data_stream, "i")
            obj_info = {"type": obj_type, "data": {}}
            try:
                with cls._temp_recursionlimit(recursion_limit):
                    HoneycomeSceneObjectLoader._dispatch_load(data_stream, obj_type, obj_info, version_str)
            except RecursionError as e:
                raise RuntimeError(f"Scene too deeply nested, increase recursion_limit. (key={key} type={obj_type})") from e
            hs.objects[key] = obj_info

        raw_blocks = []
        for _ in range(10):
            length = load_type(data_stream, "i")
            raw_blocks.append(data_stream.read(length))

        hs.frame_filename = load_string(data_stream).decode("utf-8")
        raw_blocks.append(data_stream.read(load_type(data_stream, "i")))

        hs.footer_marker = load_string(data_stream).decode("utf-8")
        remaining = data_stream.read()
        hs.unknown_tail_extra = remaining or None

        hs._raw_summary = raw_summary
        hs._raw_blocks = raw_blocks
        if decryption_key and decryption_iv:
            hs._parse_blocks(raw_summary, raw_blocks)

        return hs

    def _parse_blocks(self, raw_summary: bytes, raw_blocks: list[bytes]) -> None:
        from kkloader.HoneycomeSceneBlocks import (
            parse_background_info,
            parse_bgm_ctrl,
            parse_camera_data_array,
            parse_camera_save_data,
            parse_common_info,
            parse_env_ctrl,
            parse_key_light_info,
            parse_light_info,
            parse_map_info,
            parse_outside_sound_ctrl,
            parse_post_processing_info,
            parse_scene_summary,
        )

        dec = self._decrypt_block(raw_summary)
        self.scene_summary = parse_scene_summary(dec)

        parsers = [
            parse_map_info,
            parse_post_processing_info,
            parse_camera_save_data,
            parse_camera_data_array,
            parse_light_info,
            parse_key_light_info,
            parse_bgm_ctrl,
            parse_env_ctrl,
            parse_outside_sound_ctrl,
            parse_background_info,
            parse_common_info,
        ]
        attrs = [
            "map_info",
            "post_processing",
            "camera",
            "camera_presets",
            "chara_light",
            "key_light",
            "bgm",
            "env_sound",
            "outside_sound",
            "background",
            "common_info",
        ]

        for parser, attr, raw in zip(parsers, attrs, raw_blocks):
            setattr(self, attr, parser(self._decrypt_block(raw)))

    def save(self, filelike: str | io.BytesIO) -> None:
        """Save Honeycome scene data to a file or BytesIO object."""
        if isinstance(filelike, str):
            with open(filelike, "bw") as f:
                f.write(bytes(self))
        elif isinstance(filelike, io.BytesIO):
            filelike.write(bytes(self))
        else:
            raise ValueError(f"Unsupported output type: {type(filelike)}")

    def __bytes__(self) -> bytes:
        data_stream = io.BytesIO()

        if self.image:
            data_stream.write(self.image)

        version_bytes = self.version.encode("utf-8")
        data_stream.write(struct.pack("b", len(version_bytes)))
        data_stream.write(version_bytes)

        write_string(data_stream, self.user_id.encode("utf-8"))
        write_string(data_stream, self.data_id.encode("utf-8"))
        write_string(data_stream, self.title.encode("utf-8"))

        data_stream.write(struct.pack("i", self.language))

        if self.crypto_key and self.crypto_iv:
            from kkloader.HoneycomeSceneBlocks import (
                serialize_background_info,
                serialize_bgm_ctrl,
                serialize_camera_data_array,
                serialize_camera_save_data,
                serialize_common_info,
                serialize_env_ctrl,
                serialize_key_light_info,
                serialize_light_info,
                serialize_map_info,
                serialize_outside_sound_ctrl,
                serialize_post_processing_info,
                serialize_scene_summary,
            )

            counts = self.count_object_types()
            self.scene_summary["chara_num"] = counts.get("Character", 0)
            self.scene_summary["item_num"] = counts.get("Item", 0)
            self._write_encrypted_block(data_stream, serialize_scene_summary(self.scene_summary))

            data_stream.write(struct.pack("i", len(self.objects)))
            for key, obj_info in self.objects.items():
                data_stream.write(struct.pack("i", key))
                data_stream.write(struct.pack("i", obj_info["type"]))
                HoneycomeSceneObjectLoader._dispatch_save(data_stream, obj_info, self.version)

            serializers = [
                serialize_map_info,
                serialize_post_processing_info,
                serialize_camera_save_data,
                serialize_camera_data_array,
                serialize_light_info,
                serialize_key_light_info,
                serialize_bgm_ctrl,
                serialize_env_ctrl,
                serialize_outside_sound_ctrl,
                serialize_background_info,
            ]
            block_attrs = [
                "map_info",
                "post_processing",
                "camera",
                "camera_presets",
                "chara_light",
                "key_light",
                "bgm",
                "env_sound",
                "outside_sound",
                "background",
            ]

            for serializer, attr in zip(serializers, block_attrs):
                self._write_encrypted_block(data_stream, serializer(getattr(self, attr)))

            write_string(data_stream, (self.frame_filename or "").encode("utf-8"))
            self._write_encrypted_block(data_stream, serialize_common_info(self.common_info))
        else:
            self._write_raw_block(data_stream, self._raw_summary)

            data_stream.write(struct.pack("i", len(self.objects)))
            for key, obj_info in self.objects.items():
                data_stream.write(struct.pack("i", key))
                data_stream.write(struct.pack("i", obj_info["type"]))
                HoneycomeSceneObjectLoader._dispatch_save(data_stream, obj_info, self.version)

            for idx in range(10):
                self._write_raw_block(data_stream, self._raw_blocks[idx])

            write_string(data_stream, (self.frame_filename or "").encode("utf-8"))
            self._write_raw_block(data_stream, self._raw_blocks[10])

        write_string(data_stream, self.footer_marker.encode("utf-8"))
        if self.unknown_tail_extra:
            data_stream.write(self.unknown_tail_extra)

        return data_stream.getvalue()

    def _write_raw_block(self, stream: io.BytesIO, data: bytes) -> None:
        stream.write(struct.pack("i", len(data)))
        stream.write(data)

    def _write_encrypted_block(self, stream: io.BytesIO, compressed: bytes) -> None:
        encrypted = self._encrypt_block(compressed)
        stream.write(struct.pack("i", len(encrypted)))
        stream.write(encrypted)

    def _decrypt_block(self, data: bytes) -> bytes:
        decryptor = Cipher(algorithms.AES(self.crypto_key), modes.CBC(self.crypto_iv), backend=default_backend()).decryptor()
        return decryptor.update(data) + decryptor.finalize()

    def _encrypt_block(self, data: bytes) -> bytes:
        remainder = len(data) % 16
        if remainder:
            data += b"\x00" * (16 - remainder)
        encryptor = Cipher(algorithms.AES(self.crypto_key), modes.CBC(self.crypto_iv), backend=default_backend()).encryptor()
        return encryptor.update(data) + encryptor.finalize()

    def to_dict(self):
        return {
            "version": self.version,
            "user_id": self.user_id,
            "data_id": self.data_id,
            "title": self.title,
            "objectCount": len(self.objects),
            "scene_summary": self.scene_summary,
            "map_info": self.map_info,
            "camera": self.camera,
            "bgm": self.bgm,
            "common_info": self.common_info,
        }

    def __repr__(self):
        return f"{self.__class__.__name__}(version={self.version!r}, title={self.title!r}, objects={len(self.objects)})"
