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
    """Class for loading and parsing Honeycome scene data.

    This implementation focuses on loading objects (items and folders) only.
    Supports both load and save operations.

    Attributes:
        image: PNG image data.
        version: Scene version string.
        dataVersion: Data format version string.
        user_id: User ID string.
        data_id: Data ID string.
        title: Scene title.
        objects: Dictionary of scene objects keyed by object ID.
        unknown_tail: Remaining unparsed data (lights, camera, etc.).
    """

    def __init__(self) -> None:
        """Initialize scene data with default values."""
        self.image: bytes | None = None
        self.version: str | None = None
        self.dataVersion: str | None = None
        self.user_id: str | None = None
        self.data_id: str | None = None
        self.title: str | None = None
        self.unknown_1: int | None = None
        self.unknown_2: bytes | None = None
        self.objects: dict[int, dict[str, Any]] = {}
        self.unknown_tail: bytes = b""
        self.unknown_tail_1: bytes | None = None
        self.unknown_tail_2: bytes | None = None
        self.unknown_tail_3: bytes | None = None
        self.unknown_tail_4: bytes | None = None
        self.unknown_tail_5: bytes | None = None
        self.unknown_tail_6: bytes | None = None
        self.unknown_tail_7: bytes | None = None
        self.unknown_tail_8: bytes | None = None
        self.unknown_tail_9: bytes | None = None
        self.unknown_tail_10: bytes | None = None
        self.frame_filename: str | None = None
        self.unknown_tail_11: bytes | None = None
        self.footer_marker: str | None = None
        self.unknown_tail_extra: bytes | None = None
        self.crypto_key: bytes | None = None
        self.crypto_iv: bytes | None = None
        self.original_filename: str | None = None

    @staticmethod
    @contextmanager
    def _temp_recursionlimit(limit: int):
        # Context manager to raise recursion limit temporarily, then restore it.
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
        """
        Load Honeycome scene data from a file or bytes.

        Args:
            filelike: Path to the file, bytes, or BytesIO object containing the scene data
            decryption_key: AES key for decrypting unknown_tail blocks
            decryption_iv: AES IV for decrypting unknown_tail blocks

        Returns:
            HoneycomeSceneData: The loaded scene data
        """
        hs = cls()
        hs.crypto_key = None
        hs.crypto_iv = None
        data_stream, hs.original_filename = to_stream(filelike)

        # Read PNG image
        hs.image = get_png(data_stream)

        # Read version string
        version_str = load_string(data_stream).decode("utf-8")

        # Read Honeycome-specific header fields
        hs.user_id = load_string(data_stream).decode("utf-8")
        hs.data_id = load_string(data_stream).decode("utf-8")
        hs.title = load_string(data_stream).decode("utf-8")

        # Read unknown fields
        hs.unknown_1 = load_type(data_stream, "i")  # 1
        hs.unknown_2 = data_stream.read(load_type(data_stream, "i"))

        hs.version = version_str
        hs.dataVersion = version_str

        # Read object dictionary
        obj_count = load_type(data_stream, "i")
        for _ in range(obj_count):
            key = load_type(data_stream, "i")
            obj_type = load_type(data_stream, "i")

            # Create object info based on type
            obj_info = {"type": obj_type, "data": {}}

            # Load object data based on type (only item and folder)
            try:
                # Temporarily raise the recursion limit while loading nested objects.
                # Some scenes exceed the default depth and should not crash the whole load.
                with cls._temp_recursionlimit(recursion_limit):
                    HoneycomeSceneObjectLoader._dispatch_load(data_stream, obj_type, obj_info, version_str)
            except RecursionError as e:
                raise RuntimeError(f"This scene is too deeply nested, so please increase `recursion_limit`. (object key={key} type={obj_type})") from e

            hs.objects[key] = obj_info

        # Read remaining data as unknown_tail (lights, camera, etc.)
        for idx in range(10):
            length = load_type(data_stream, "i")
            block = data_stream.read(length)
            setattr(hs, f"unknown_tail_{idx + 1}", block)

        # Read filename of frame
        hs.frame_filename = load_string(data_stream).decode("utf-8")

        hs.unknown_tail_11 = data_stream.read(load_type(data_stream, "i"))

        # 【DigitalCraft】
        hs.footer_marker = load_string(data_stream).decode("utf-8")

        # this byte is basically zero-length, but may contain mod data.
        remaining = data_stream.read()
        hs.unknown_tail_extra = remaining or None

        hs.crypto_key = decryption_key
        hs.crypto_iv = decryption_iv
        if decryption_key and decryption_iv:
            if len(decryption_key) != 16 or len(decryption_iv) != 16:
                raise ValueError("Invalid decryption key or initialization vector.")

            hs.unknown_2 = hs._decrypt_unknown(hs.unknown_2, decryption_key, decryption_iv)
            for idx in range(11):
                block = getattr(hs, f"unknown_tail_{idx + 1}") or b""
                decrypted = hs._decrypt_unknown(block, decryption_key, decryption_iv)
                setattr(hs, f"unknown_tail_{idx + 1}", decrypted)

        return hs

    def save(self, filelike: str | io.BytesIO) -> None:
        """
        Save Honeycome scene data to a file or BytesIO object.

        Args:
            filelike: Path to the file or BytesIO object to save the scene data to
        """
        if isinstance(filelike, str):
            with open(filelike, "bw") as f:
                f.write(bytes(self))
        elif isinstance(filelike, io.BytesIO):
            filelike.write(bytes(self))
        else:
            raise ValueError(f"Unsupported output type: {type(filelike)}")

    def __bytes__(self) -> bytes:
        """
        Convert the scene data to bytes.

        Returns:
            bytes: The scene data as bytes
        """
        data_stream = io.BytesIO()

        # Write PNG data if available
        if self.image:
            data_stream.write(self.image)

        # Write version string
        version_bytes = self.version.encode("utf-8")
        data_stream.write(struct.pack("b", len(version_bytes)))
        data_stream.write(version_bytes)

        # Write Honeycome-specific header fields
        write_string(data_stream, self.user_id.encode("utf-8"))
        write_string(data_stream, self.data_id.encode("utf-8"))
        write_string(data_stream, self.title.encode("utf-8"))

        # Write unknown fields
        data_stream.write(struct.pack("i", self.unknown_1))
        unknown_2 = self.unknown_2
        if self.crypto_key is not None and self.crypto_iv is not None:
            unknown_2 = self._encrypt_unknown(unknown_2)
        data_stream.write(struct.pack("i", len(unknown_2)))
        data_stream.write(unknown_2)

        # Write object dictionary
        data_stream.write(struct.pack("i", len(self.objects)))
        for key, obj_info in self.objects.items():
            data_stream.write(struct.pack("i", key))
            data_stream.write(struct.pack("i", obj_info["type"]))

            # Save object data based on type
            try:
                HoneycomeSceneObjectLoader._dispatch_save(data_stream, obj_info, self.version)
            except NotImplementedError as e:
                raise NotImplementedError(f"Cannot save object of type {obj_info['type']}: {str(e)}")

        # Write unknown_tail (lights, camera, etc.)
        for idx in range(10):
            block = getattr(self, f"unknown_tail_{idx + 1}") or b""
            if self.crypto_key is not None and self.crypto_iv is not None:
                block = self._encrypt_unknown(block)
            length = len(block)
            data_stream.write(struct.pack("i", length))
            data_stream.write(block)

        write_string(data_stream, (self.frame_filename or "").encode("utf-8"))
        unknown_tail_11 = self.unknown_tail_11
        if self.crypto_key is not None and self.crypto_iv is not None:
            unknown_tail_11 = self._encrypt_unknown(unknown_tail_11)
        data_stream.write(struct.pack("i", len(unknown_tail_11)))
        data_stream.write(unknown_tail_11)
        write_string(data_stream, self.footer_marker.encode("utf-8"))

        if self.unknown_tail_extra:
            data_stream.write(self.unknown_tail_extra)

        return data_stream.getvalue()

    def _decrypt_unknown(self, data: bytes, decryption_key: bytes, decryption_iv: bytes) -> bytes:
        decryptor = Cipher(algorithms.AES(decryption_key), modes.CBC(decryption_iv), backend=default_backend()).decryptor()
        return decryptor.update(data) + decryptor.finalize()

    def _encrypt_unknown(self, data: bytes) -> bytes:
        encryptor = Cipher(algorithms.AES(self.crypto_key), modes.CBC(self.crypto_iv), backend=default_backend()).encryptor()
        return encryptor.update(data) + encryptor.finalize()

    def to_dict(self):
        """Convert the scene data to a dictionary"""
        return {
            "version": self.version,
            "dataVersion": self.dataVersion,
            "user_id": self.user_id,
            "data_id": self.data_id,
            "title": self.title,
            "objectCount": len(self.objects),
        }

    def __str__(self):
        """String representation of the scene data"""
        return f"HoneycomeSceneData(version={self.version}, objects={len(self.objects)})"

    def __repr__(self):
        """Return a concise debug representation of Honeycome scene data."""
        return f"{self.__class__.__name__}(version={self.version!r}, title={self.title!r}, user_id={self.user_id!r}, data_id={self.data_id!r}, original_filename={self.original_filename!r}, footer_marker={self.footer_marker!r})"
