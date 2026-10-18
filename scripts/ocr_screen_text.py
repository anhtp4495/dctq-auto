"""Recognize three game options and two buttons, including screen coordinates."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pytesseract
from adbutils import adb
from PIL import Image, ImageOps
from pytesseract import TesseractNotFoundError

OPTION_REGIONS = (
    ("Option 1", 350, 250, 380, 500),
    ("Option 2", 760, 250, 380, 500),
    ("Option 3", 1160, 250, 400, 500),
)
# Each tuple: label, left, top, width, height.
BUTTON_REGIONS = (
    ("Làm mới (Miễn Phí)", 400, 820, 500, 180),
    ("Xác Nhận", 1000, 820, 500, 180),
)


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def get_screen_image(
    image: str | Path | Image.Image | None = None,
    *,
    serial: str = "emulator-5554",
    screenshot_path: str | Path | None = "screenshots/ocr_screen.png",
) -> Image.Image:
    """Return an RGB image. Use the supplied image if present; otherwise capture via ADB."""
    if isinstance(image, Image.Image):
        result = image.convert("RGB")
    elif image is not None:
        with Image.open(image) as source:
            result = source.convert("RGB")
    else:
        device = adb.device(serial=serial)
        if device.get_state() != "device":
            raise RuntimeError(f"ADB device {serial!r} is not online.")
        result = device.screenshot().convert("RGB")

    if screenshot_path is not None:
        path = Path(screenshot_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        result.save(path)
    return result


def _ocr_region(
    crop: Image.Image, lang: str, *, button: bool = False
) -> list[dict[str, Any]]:
    """OCR a crop and return text, confidence and crop-local boxes."""
    scale = 3
    processed = crop.resize(
        (crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS
    )
    processed = ImageOps.autocontrast(ImageOps.grayscale(processed))
    modes = (6, 11, 12) if button else (11,)
    tokens: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[int, int, int, int]]] = set()

    for psm in modes:
        data = pytesseract.image_to_data(
            processed, lang=lang, config=f"--psm {psm}",
            output_type=pytesseract.Output.DICT,
        )
        for i, raw_text in enumerate(data["text"]):
            text = raw_text.strip()
            try:
                confidence = float(data["conf"][i])
            except (TypeError, ValueError):
                continue
            if not text or confidence < (10 if button else 20):
                continue
            box = (
                int(data["left"][i] / scale),
                int(data["top"][i] / scale),
                int(data["width"][i] / scale),
                int(data["height"][i] / scale),
            )
            key = (text.lower(), box)
            if key in seen:
                continue
            seen.add(key)
            tokens.append({
                "text": text,
                "confidence": round(confidence, 1),
                "box": {"x": box[0], "y": box[1], "w": box[2], "h": box[3]},
            })
    return tokens


def _absolute_tokens(
    tokens: list[dict[str, Any]], left: int, top: int
) -> list[dict[str, Any]]:
    result = []
    for token in tokens:
        box = token["box"]
        result.append({
            **token,
            "box": {
                "x": left + box["x"],
                "y": top + box["y"],
                "w": box["w"],
                "h": box["h"],
            },
        })
    return result


def recognize_game_screen(
    image: str | Path | Image.Image | None = None,
    *,
    serial: str = "emulator-5554",
    lang: str = "vie+eng",
    tesseract_cmd: str | None = None,
    screenshot_path: str | Path | None = "screenshots/ocr_screen.png",
) -> dict[str, Any]:
    """Return OCR for all 3 options and 2 buttons, with absolute screen coordinates.

    Pass a PIL image or image path to reuse an existing screenshot. If image=None,
    a fresh screenshot is captured from the requested ADB device.
    """
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    screen = get_screen_image(image, serial=serial, screenshot_path=screenshot_path)
    screen_width, screen_height = screen.size
    output: dict[str, Any] = {
        "screen_size": {"width": screen_width, "height": screen_height},
        "options": [],
        "buttons": [],
    }

    for label, left, top, width, height in OPTION_REGIONS:
        right, bottom = min(left + width, screen_width), min(top + height, screen_height)
        if left < 0 or top < 0 or left >= right or top >= bottom:
            tokens = []
        else:
            crop = screen.crop((left, top, right, bottom))
            tokens = _absolute_tokens(_ocr_region(crop, lang), left, top)
        output["options"].append({
            "label": label,
            "region": {"x": left, "y": top, "w": right - left, "h": bottom - top},
            "text": " ".join(token["text"] for token in tokens),
            "tokens": tokens,
        })

    for label, left, top, width, height in BUTTON_REGIONS:
        right, bottom = min(left + width, screen_width), min(top + height, screen_height)
        if left < 0 or top < 0 or left >= right or top >= bottom:
            tokens = []
        else:
            crop = screen.crop((left, top, right, bottom))
            tokens = _absolute_tokens(_ocr_region(crop, lang, button=True), left, top)
        normalized = _normalize_text(" ".join(token["text"] for token in tokens))
        if label.startswith("Làm mới"):
            detected = (
                ("lam" in normalized or "3m" in normalized or "u3m" in normalized)
                and "moi" in normalized
                and "mien" in normalized
                and "phi" in normalized
            )
        else:
            detected = "xacinhan" in normalized or (
                "xac" in normalized and "nhan" in normalized
            )
        output["buttons"].append({
            "label": label,
            "detected": detected,
            "region": {"x": left, "y": top, "w": right - left, "h": bottom - top},
            "text": " ".join(token["text"] for token in tokens),
            "tokens": tokens,
        })

    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recognize three game options and two buttons; report absolute coordinates."
    )
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--lang", default="vie+eng", help="Tesseract languages, e.g. vie+eng")
    parser.add_argument("--image", help="Existing screenshot path; if omitted, capture from ADB")
    parser.add_argument("--output", default="screenshots/ocr_screen.png",
                        help="Where to save the screenshot (use empty string to disable)")
    parser.add_argument("--tesseract-cmd", help="Path to tesseract.exe if it is not on PATH")
    args = parser.parse_args()

    try:
        result = recognize_game_screen(
            image=args.image,
            serial=args.serial,
            lang=args.lang,
            tesseract_cmd=args.tesseract_cmd,
            screenshot_path=args.output or None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except TesseractNotFoundError:
        print("Tesseract not found. Install it or pass --tesseract-cmd.", file=sys.stderr)
        return 1
    except pytesseract.TesseractError as exc:
        print(f"OCR failed: {exc}. Check that language data for {args.lang!r} is installed.",
              file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Could not capture or OCR the screen: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
