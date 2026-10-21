"""Shared OCR helper with white-on-dark defaults."""
DEFAULT_OCR_CONFIG = {
    "method": "color_text",
    "text_color": "#FFFFFF",
    "background_color": "#202020",
    "border_color": None,
    "color_tolerance": 38,
    "psm": 11,
    "lang": "vie+eng",
}

import json
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
import pytesseract
from PIL import Image

_CONFIG_FILE = Path(__file__).resolve().parents[1] / "tasks" / "common" / "ocr_regions.json"

def _parse_color(value):
    if value is None or value == "":
        return None
    if isinstance(value, (tuple, list)):
        rgb = tuple(int(v) for v in value)
    elif value.startswith("#") and len(value) == 7:
        rgb = tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    else:
        rgb = tuple(int(v.strip()) for v in value.split(","))
    if len(rgb) != 3 or any(v < 0 or v > 255 for v in rgb):
        raise ValueError(f"Invalid RGB color: {value}")
    return rgb

@lru_cache(maxsize=1)
def _load_regions():
    if not _CONFIG_FILE.exists():
        return {}
    with _CONFIG_FILE.open(encoding="utf-8") as stream:
        return json.load(stream).get("regions", {})

def get_ocr_config(region_key=None, override=None):
    config = {**DEFAULT_OCR_CONFIG, **_load_regions().get(region_key, {}), **(override or {})}
    raw = config["psm"]
    config["psm"] = [int(p) for p in raw] if isinstance(raw, list) else [int(raw)]
    if not config["psm"] or any(p < 0 or p > 13 for p in config["psm"]):
        raise ValueError("Invalid PSM")
    for key in ("text_color", "background_color", "border_color"):
        config[key] = _parse_color(config.get(key))
    if config["text_color"] is None or config["background_color"] is None:
        raise ValueError("text_color and background_color are required")
    return config

def _color_distance(rgb, color):
    ref = cv2.cvtColor(np.uint8([[list(color)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    return np.linalg.norm(lab - ref, axis=2)

def preprocess_region(crop, config):
    """Prepare a crop for Tesseract using the selected OCR method."""
    if isinstance(crop, Image.Image):
        rgb = np.asarray(crop.convert("RGB"))
    else:
        array = np.asarray(crop)
        if array.ndim == 2:
            rgb = cv2.cvtColor(array, cv2.COLOR_GRAY2RGB)
        elif array.ndim == 3 and array.shape[2] == 3:
            rgb = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
        else:
            raise ValueError(f"Unsupported image shape: {array.shape}")
    scale = int(config.get("scale", 3))
    method = config.get("method", "color_text")
    if method == "grayscale":
        output = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(
            cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
        if scale > 1:
            output = cv2.resize(output, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    elif method == "color_text":
        tolerance = float(config.get("color_tolerance", 38))
        profiles = config.get("color_profiles") or [{
            "text_color": config["text_color"],
            "background_color": config["background_color"],
            "border_color": config.get("border_color"),
            "color_tolerance": tolerance,
        }]
        mask = np.zeros(rgb.shape[:2], dtype=bool)
        for profile in profiles:
            text_color = _parse_color(profile.get("text_color"))
            background_color = _parse_color(profile.get("background_color"))
            if text_color is None or background_color is None:
                continue
            profile_tolerance = float(profile.get("color_tolerance", tolerance))
            text_distance = _color_distance(rgb, text_color)
            background_distance = _color_distance(rgb, background_color)
            profile_mask = (text_distance <= profile_tolerance) & (text_distance < background_distance)
            border_color = _parse_color(profile.get("border_color"))
            if border_color is not None:
                profile_mask &= _color_distance(rgb, border_color) > profile_tolerance
            mask |= profile_mask
        output = np.where(mask, 0, 255).astype(np.uint8)
        if scale > 1:
            output = cv2.resize(output, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    else:
        raise ValueError(f"Unsupported OCR method: {method}")
    return cv2.copyMakeBorder(output, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255)

def read_region_ocr(crop, *, region_key=None, lang=None, override=None):
    """Return OCR tokens with confidence and boxes relative to the crop."""
    config = get_ocr_config(region_key, override)
    image = preprocess_region(crop, config)
    scale = int(config.get("scale", 3))
    results, seen = [], set()
    for psm in config["psm"]:
        data = pytesseract.image_to_data(
            image, lang=lang or config.get("lang", "vie+eng"),
            config=f"--oem 3 --psm {psm}", output_type=pytesseract.Output.DICT)
        for index, raw_text in enumerate(data["text"]):
            word = raw_text.strip()
            try:
                confidence = float(data["conf"][index])
            except (ValueError, TypeError):
                continue
            if not word or confidence < float(config.get("min_confidence", 10)):
                continue
            box = (
                max(0, int((int(data["left"][index]) - 18) / scale)),
                max(0, int((int(data["top"][index]) - 18) / scale)),
                max(0, round(int(data["width"][index]) / scale)),
                max(0, round(int(data["height"][index]) / scale)),
            )
            key = (word.lower(), box)
            if key in seen:
                continue
            seen.add(key)
            results.append({"text": word, "confidence": round(confidence, 1),
                "box": {"x": box[0], "y": box[1], "w": box[2], "h": box[3]}, "psm": psm})
    return results
