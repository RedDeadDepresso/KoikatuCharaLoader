"""Structured parsers for Honeycome scene encrypted blocks.

Pipeline overview:
  Load:  AES-CBC decrypt -> Brotli decompress (rstrip zeros) -> MemoryPack parse
  Save:  MemoryPack serialize -> Brotli compress -> AES-CBC encrypt (zero-pad to 16B)

parse_* functions accept raw decrypted bytes (post-AES, pre-decompress).
serialize_* functions return Brotli-compressed bytes (ready for AES encryption + padding).
"""

from __future__ import annotations

from kkloader.MemoryPack import MpReader, MpWriter

import brotli


def decompress_block(data: bytes) -> bytes:
    """Brotli decompress a decrypted block (handles trailing zero-padding from AES).

    AES-CBC with PaddingMode.Zeros appends up to 15 zero-bytes. If the Brotli
    stream itself ends with 0x00, simple rstrip would over-strip. We try
    progressively longer candidates until decompression succeeds.
    """
    try:
        return brotli.decompress(data)
    except brotli.error:
        pass
    stripped = data.rstrip(b"\x00")
    for extra in range(min(16, len(data) - len(stripped) + 1)):
        try:
            return brotli.decompress(stripped + data[len(stripped) : len(stripped) + extra])
        except brotli.error:
            continue
    raise ValueError(f"Cannot decompress block (len={len(data)}, stripped={len(stripped)})")


def compress_block(data: bytes) -> bytes:
    """Brotli compress MemoryPack bytes for encryption."""
    return brotli.compress(data, quality=11, lgwin=22)


# ============================================================
# Reader helpers
# ============================================================


def _read_vector3(r: MpReader) -> dict:
    return {"x": r.f32(), "y": r.f32(), "z": r.f32()}


def _read_color(r: MpReader) -> dict:
    return {"r": r.f32(), "g": r.f32(), "b": r.f32(), "a": r.f32()}


def _read_change_amount(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "pos": _read_vector3(r),
        "rot": _read_vector3(r),
        "scale": _read_vector3(r),
    }


def _read_float_array(r: MpReader) -> list[float] | None:
    n = r.collection_header()
    if n is None:
        return None
    return [r.f32() for _ in range(n)]


# ============================================================
# Writer helpers
# ============================================================


def _write_vector3(w: MpWriter, v: dict) -> None:
    w.f32(v["x"])
    w.f32(v["y"])
    w.f32(v["z"])


def _write_color(w: MpWriter, c: dict) -> None:
    w.f32(c["r"])
    w.f32(c["g"])
    w.f32(c["b"])
    w.f32(c["a"])


def _write_change_amount(w: MpWriter, ca: dict | None) -> None:
    if ca is None:
        w.object_header(None)
        return
    w.object_header(3)
    _write_vector3(w, ca["pos"])
    _write_vector3(w, ca["rot"])
    _write_vector3(w, ca["scale"])


def _write_float_array(w: MpWriter, arr: list[float] | None) -> None:
    if arr is None:
        w.i32(-1)
        return
    w.i32(len(arr))
    for v in arr:
        w.f32(v)


# ============================================================
# SceneSummary (unknown_2)
# ============================================================


def parse_scene_summary(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    hdr = r.object_header()
    result = {
        "chara_num": r.i32(),
        "item_num": r.i32(),
        "map": r.i32(),
    }
    if hdr >= 4:
        n = r.collection_header()
        result["titles"] = [r.i32() for _ in range(n)] if n is not None else None
    else:
        result["titles"] = None
    return result


def serialize_scene_summary(d: dict) -> bytes:
    w = MpWriter()
    titles = d.get("titles")
    w.object_header(4 if titles is not None else 3)
    w.i32(d["chara_num"])
    w.i32(d["item_num"])
    w.i32(d["map"])
    if titles is not None:
        w.i32(len(titles))
        for t in titles:
            w.i32(t)
    return compress_block(w.bytes())


# ============================================================
# MapInfo (tail_1)
# ============================================================


def parse_map_info(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "no": r.i32(),
        "amount": _read_change_amount(r),
        "option": r.boolean(),
        "light": r.boolean(),
    }


def serialize_map_info(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(4)
    w.i32(d["no"])
    _write_change_amount(w, d["amount"])
    w.boolean(d["option"])
    w.boolean(d["light"])
    return compress_block(w.bytes())


# ============================================================
# CameraSaveData (tail_3)
# ============================================================


def parse_camera_save_data(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "pos": _read_vector3(r),
        "rotate": _read_vector3(r),
        "distance": _read_vector3(r),
        "parse": r.f32(),
    }


def serialize_camera_save_data(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(4)
    _write_vector3(w, d["pos"])
    _write_vector3(w, d["rotate"])
    _write_vector3(w, d["distance"])
    w.f32(d["parse"])
    return compress_block(w.bytes())


# ============================================================
# CameraData[] (tail_4) — array of CameraSaveData
# ============================================================


def parse_camera_data_array(data: bytes) -> list[dict]:
    r = MpReader(decompress_block(data))
    n = r.collection_header()
    if n is None:
        return []
    result = []
    for _ in range(n):
        r.object_header()
        result.append(
            {
                "pos": _read_vector3(r),
                "rotate": _read_vector3(r),
                "distance": _read_vector3(r),
                "parse": r.f32(),
            }
        )
    return result


def serialize_camera_data_array(items: list[dict]) -> bytes:
    w = MpWriter()
    w.i32(len(items))
    for d in items:
        w.object_header(4)
        _write_vector3(w, d["pos"])
        _write_vector3(w, d["rotate"])
        _write_vector3(w, d["distance"])
        w.f32(d["parse"])
    return compress_block(w.bytes())


# ============================================================
# LightInfo / CharaLight (tail_5)
# ============================================================


def parse_light_info(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "color": _read_color(r),
        "intensity": r.f32(),
        "rot": _read_float_array(r),
    }


def serialize_light_info(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(3)
    _write_color(w, d["color"])
    w.f32(d["intensity"])
    _write_float_array(w, d["rot"])
    return compress_block(w.bytes())


# ============================================================
# KeyLightInfo (tail_6)
# ============================================================


def parse_key_light_info(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "enable": r.boolean(),
        "color": _read_color(r),
        "intensity": r.f32(),
        "shadow": r.boolean(),
        "shadow_strength": r.f32(),
        "rot": _read_float_array(r),
        "sync": r.boolean(),
        "parent_rotation": _read_vector3(r),
    }


def serialize_key_light_info(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(8)
    w.boolean(d["enable"])
    _write_color(w, d["color"])
    w.f32(d["intensity"])
    w.boolean(d["shadow"])
    w.f32(d["shadow_strength"])
    _write_float_array(w, d["rot"])
    w.boolean(d["sync"])
    _write_vector3(w, d["parent_rotation"])
    return compress_block(w.bytes())


# ============================================================
# BGMCtrl (tail_7)
# ============================================================


def parse_bgm_ctrl(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "play": r.boolean(),
        "loop": r.boolean(),
        "no": r.i32(),
        "title": r.i32(),
    }


def serialize_bgm_ctrl(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(4)
    w.boolean(d["play"])
    w.boolean(d["loop"])
    w.i32(d["no"])
    w.i32(d["title"])
    return compress_block(w.bytes())


# ============================================================
# ENVCtrl (tail_8) — same structure as BGMCtrl
# ============================================================

parse_env_ctrl = parse_bgm_ctrl
serialize_env_ctrl = serialize_bgm_ctrl


# ============================================================
# OutsideSoundCtrl (tail_9)
# ============================================================


def parse_outside_sound_ctrl(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "play": r.boolean(),
        "loop": r.boolean(),
        "file": r.string(),
    }


def serialize_outside_sound_ctrl(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(3)
    w.boolean(d["play"])
    w.boolean(d["loop"])
    w.string(d["file"])
    return compress_block(w.bytes())


# ============================================================
# BackgroundInfo (tail_10)
# ============================================================


def parse_background_info(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "directory_type": r.i32(),
        "file": r.string(),
    }


def serialize_background_info(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(2)
    w.i32(d["directory_type"])
    w.string(d["file"])
    return compress_block(w.bytes())


# ============================================================
# SceneCommonInfo / CommonInfo (tail_11)
# ============================================================


def parse_common_info(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "item_lamp": r.i32(),
        "chara_scale_limit": r.i32(),
    }


def serialize_common_info(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(2)
    w.i32(d["item_lamp"])
    w.i32(d["chara_scale_limit"])
    return compress_block(w.bytes())


# ============================================================
# PostProcessingInfo (tail_2) — 13 nested objects
# ============================================================


def _read_pp_background(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {"type": r.i32(), "color": _read_color(r)}


def _read_pp_env_lighting(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "source": r.i32(),
        "skybox_material": r.i32(),
        "intensity_multiplier": r.f32(),
        "sky_color": _read_color(r),
        "equator_color": _read_color(r),
        "ground_color": _read_color(r),
        "ambient_color": _read_color(r),
    }


def _read_pp_color_adjustments(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "post_exposure": r.f32(),
        "contrast": r.f32(),
        "color_filter": _read_color(r),
        "hue_shift": r.f32(),
        "saturation": r.f32(),
    }


def _read_pp_color_lookup(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "lookup_texture": r.i32(),
        "intensity": r.f32(),
    }


def _read_pp_beautify(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {"sharpen": r.f32()}


def _read_pp_fog(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "density": r.f32(),
        "color": _read_color(r),
    }


def _read_pp_bloom(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "intensity": r.f32(),
        "threshold": r.f32(),
    }


def _read_pp_ambient_occlusion(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "intensity": r.f32(),
        "direct_light_strength": r.f32(),
        "radius": r.f32(),
    }


def _read_pp_depth_of_field(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "focal_length": r.f32(),
        "aperture": r.f32(),
        "transparent_support": r.boolean(),
        "depth_of_field_target": r.i32(),
    }


def _read_pp_vignette(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "outer_ring": r.f32(),
        "inner_ring": r.f32(),
        "tint_color": _read_color(r),
    }


def _read_pp_chromatic_aberration(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {"enable": r.boolean(), "intensity": r.f32()}


def _read_pp_sun_flares(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {
        "enable": r.boolean(),
        "global_intensity": r.f32(),
        "tint_color": _read_color(r),
    }


def _read_pp_film_grain(r: MpReader) -> dict | None:
    hdr = r.object_header()
    if hdr is None:
        return None
    return {"enable": r.boolean(), "intensity": r.f32()}


def parse_post_processing_info(data: bytes) -> dict:
    r = MpReader(decompress_block(data))
    r.object_header()
    return {
        "background": _read_pp_background(r),
        "environment_lighting": _read_pp_env_lighting(r),
        "color_adjustments": _read_pp_color_adjustments(r),
        "color_lookup": _read_pp_color_lookup(r),
        "beautify": _read_pp_beautify(r),
        "fog": _read_pp_fog(r),
        "bloom": _read_pp_bloom(r),
        "ambient_occlusion": _read_pp_ambient_occlusion(r),
        "depth_of_field": _read_pp_depth_of_field(r),
        "vignette": _read_pp_vignette(r),
        "chromatic_aberration": _read_pp_chromatic_aberration(r),
        "sun_flares": _read_pp_sun_flares(r),
        "film_grain": _read_pp_film_grain(r),
    }


def serialize_post_processing_info(d: dict) -> bytes:
    w = MpWriter()
    w.object_header(13)

    bg = d.get("background")
    if bg is None:
        w.object_header(None)
    else:
        w.object_header(2)
        w.i32(bg["type"])
        _write_color(w, bg["color"])

    el = d.get("environment_lighting")
    if el is None:
        w.object_header(None)
    else:
        w.object_header(7)
        w.i32(el["source"])
        w.i32(el["skybox_material"])
        w.f32(el["intensity_multiplier"])
        _write_color(w, el["sky_color"])
        _write_color(w, el["equator_color"])
        _write_color(w, el["ground_color"])
        _write_color(w, el["ambient_color"])

    ca = d.get("color_adjustments")
    if ca is None:
        w.object_header(None)
    else:
        w.object_header(5)
        w.f32(ca["post_exposure"])
        w.f32(ca["contrast"])
        _write_color(w, ca["color_filter"])
        w.f32(ca["hue_shift"])
        w.f32(ca["saturation"])

    cl = d.get("color_lookup")
    if cl is None:
        w.object_header(None)
    else:
        w.object_header(3)
        w.boolean(cl["enable"])
        w.i32(cl["lookup_texture"])
        w.f32(cl["intensity"])

    bt = d.get("beautify")
    if bt is None:
        w.object_header(None)
    else:
        w.object_header(1)
        w.f32(bt["sharpen"])

    fg = d.get("fog")
    if fg is None:
        w.object_header(None)
    else:
        w.object_header(3)
        w.boolean(fg["enable"])
        w.f32(fg["density"])
        _write_color(w, fg["color"])

    bl = d.get("bloom")
    if bl is None:
        w.object_header(None)
    else:
        w.object_header(3)
        w.boolean(bl["enable"])
        w.f32(bl["intensity"])
        w.f32(bl["threshold"])

    ao = d.get("ambient_occlusion")
    if ao is None:
        w.object_header(None)
    else:
        w.object_header(4)
        w.boolean(ao["enable"])
        w.f32(ao["intensity"])
        w.f32(ao["direct_light_strength"])
        w.f32(ao["radius"])

    dof = d.get("depth_of_field")
    if dof is None:
        w.object_header(None)
    else:
        w.object_header(5)
        w.boolean(dof["enable"])
        w.f32(dof["focal_length"])
        w.f32(dof["aperture"])
        w.boolean(dof["transparent_support"])
        w.i32(dof["depth_of_field_target"])

    vg = d.get("vignette")
    if vg is None:
        w.object_header(None)
    else:
        w.object_header(4)
        w.boolean(vg["enable"])
        w.f32(vg["outer_ring"])
        w.f32(vg["inner_ring"])
        _write_color(w, vg["tint_color"])

    cr = d.get("chromatic_aberration")
    if cr is None:
        w.object_header(None)
    else:
        w.object_header(2)
        w.boolean(cr["enable"])
        w.f32(cr["intensity"])

    sf = d.get("sun_flares")
    if sf is None:
        w.object_header(None)
    else:
        w.object_header(3)
        w.boolean(sf["enable"])
        w.f32(sf["global_intensity"])
        _write_color(w, sf["tint_color"])

    fg2 = d.get("film_grain")
    if fg2 is None:
        w.object_header(None)
    else:
        w.object_header(2)
        w.boolean(fg2["enable"])
        w.f32(fg2["intensity"])

    return compress_block(w.bytes())
