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
