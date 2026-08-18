import io
import struct

from kkloader.funcs import compare_versions, get_png, get_png_length, has_png_magic, load_string, to_stream, write_string

import pytest


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("0.0.10", "0.0.5.2", 1),
        ("0.0.5.2", "0.0.10", -1),
        ("0.0.5.2", "0.0.5.2", 0),
        ("1.0.0", "1.0", 0),
        ("0.0.3", "0.0.3", 0),
        ("0.0.4", "0.0.3", 1),
        ("0.0.2", "0.0.3", -1),
        ("1.2.3.4", "1.2.3.4", 0),
        ("1.2.3.5", "1.2.3.4", 1),
        ("1.1.2.1", "1.1.2.0", 1),
    ],
)
def test_compare_versions(a, b, expected):
    assert compare_versions(a, b) == expected


@pytest.mark.parametrize("length", [0, 1, 127, 128, 255, 16384])
def test_write_read_string_roundtrip(length):
    data = b"A" * length
    stream = io.BytesIO()
    write_string(stream, data)
    stream.seek(0)
    result = load_string(stream)
    assert result == data


def test_to_stream_str(tmp_path):
    p = tmp_path / "test.bin"
    p.write_bytes(b"hello")
    stream, path = to_stream(str(p))
    assert stream.read() == b"hello"
    assert path == str(p.resolve())


def test_to_stream_path(tmp_path):
    p = tmp_path / "test.bin"
    p.write_bytes(b"hello")
    stream, path = to_stream(p)
    assert stream.read() == b"hello"
    assert path == str(p.resolve())


def test_to_stream_bytes():
    stream, path = to_stream(b"hello")
    assert stream.read() == b"hello"
    assert path is None


def test_to_stream_bytesio():
    bio = io.BytesIO(b"hello")
    stream, path = to_stream(bio)
    assert stream is bio
    assert path is None


def test_to_stream_invalid():
    with pytest.raises(ValueError, match="unsupported input"):
        to_stream(123)


def _make_minimal_png() -> bytes:
    magic = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = 0
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0)
    return magic + ihdr_chunk + iend_chunk


def test_has_png_magic_true():
    png = _make_minimal_png()
    stream = io.BytesIO(png)
    assert has_png_magic(stream)
    assert stream.tell() == 0


def test_has_png_magic_false():
    stream = io.BytesIO(b"\x00\x01\x02\x03\x04\x05\x06\x07")
    assert not has_png_magic(stream)
    assert stream.tell() == 0


def test_get_png_extracts_full_image():
    png = _make_minimal_png()
    trailing = b"extra data after png"
    stream = io.BytesIO(png + trailing)
    result = get_png(stream)
    assert result == png
    assert stream.tell() == len(png)


def test_get_png_length():
    png = _make_minimal_png()
    assert get_png_length(png) == len(png)


def test_get_png_from_real_file(chara_dir):
    with open(chara_dir / "kk_chara.png", "rb") as f:
        stream = io.BytesIO(f.read())
    png_data = get_png(stream)
    assert png_data[:8] == b"\x89PNG\r\n\x1a\n"
    assert b"IEND" in png_data[-12:]
    assert stream.tell() == len(png_data)
