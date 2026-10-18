"""Nhận diện 3 thẻ lựa chọn và 2 nút ở màn hình chọn nâng cấp trong game.

API công khai:
- get_screen_image(): dùng ảnh truyền vào nếu có; nếu không thì chụp qua ADB.
- recognize_game_options(): trả về 3 options + 2 buttons, kèm tọa độ tuyệt đối.

Tọa độ box có dạng (x, y, w, h), gốc (0, 0) ở góc trên-trái màn hình.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pytesseract
from PIL import Image, ImageOps

from dctq_auto.adb.client import AdbClient

OPTION_REGIONS = (
    ("Option 1", 350, 250, 380, 500),
    ("Option 2", 760, 250, 380, 500),
    ("Option 3", 1160, 250, 400, 500),
)
# Mỗi vùng: (label, left, top, width, height) trên màn hình 1920x1080.
BUTTON_REGIONS = (
    ("Làm mới (Miễn Phí)", 400, 820, 500, 180),
    ("Xác Nhận", 1000, 820, 500, 180),
)


def get_screen_image(
    image: Image.Image | np.ndarray | str | Path | None = None,
    *,
    serial: str = "emulator-5554",
) -> Image.Image:
    """Chuẩn hóa ảnh đầu vào thành PIL RGB; chỉ chụp ADB khi image=None.

    image hỗ trợ PIL.Image, numpy.ndarray (ảnh OpenCV BGR hoặc grayscale),
    đường dẫn file ảnh, hoặc None để chụp màn hình emulator qua ADB.
    """
    if image is None:
        device = AdbClient(serial=serial).connect()
        return device.screenshot().convert("RGB")

    if isinstance(image, Image.Image):
        return image.convert("RGB")

    if isinstance(image, (str, Path)):
        with Image.open(image) as source:
            return source.convert("RGB")

    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return Image.fromarray(image).convert("RGB")
        if image.ndim == 3 and image.shape[2] == 3:
            # Vision utilities trong project sử dụng OpenCV BGR.
            return Image.fromarray(image[:, :, ::-1].copy()).convert("RGB")
        if image.ndim == 3 and image.shape[2] == 4:
            # OpenCV BGRA -> RGBA.
            return Image.fromarray(image[:, :, [2, 1, 0, 3]].copy()).convert("RGB")
        raise ValueError(f"Định dạng numpy image không hỗ trợ: shape={image.shape}")

    raise TypeError("image phải là PIL.Image, numpy.ndarray, đường dẫn ảnh hoặc None.")


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _read_region(
    crop: Image.Image, *, lang: str, is_button: bool
) -> list[dict[str, Any]]:
    scale = 3
    processed = crop.resize(
        (crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS
    )
    processed = ImageOps.autocontrast(ImageOps.grayscale(processed))
    psm_modes = (6, 11, 12) if is_button else (11,)
    tokens: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[int, int, int, int]]] = set()

    for psm in psm_modes:
        data = pytesseract.image_to_data(
            processed,
            lang=lang,
            config=f"--psm {psm}",
            output_type=pytesseract.Output.DICT,
        )
        for index, raw_text in enumerate(data["text"]):
            text = raw_text.strip()
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                continue
            if not text or confidence < (10 if is_button else 20):
                continue

            box = (
                int(data["left"][index] / scale),
                int(data["top"][index] / scale),
                int(data["width"][index] / scale),
                int(data["height"][index] / scale),
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


def _make_absolute(tokens: list[dict[str, Any]], left: int, top: int) -> list[dict[str, Any]]:
    absolute = []
    for token in tokens:
        box = token["box"]
        absolute.append({
            **token,
            "box": {
                "x": left + box["x"],
                "y": top + box["y"],
                "w": box["w"],
                "h": box["h"],
            },
        })
    return absolute


def _button_detected(label: str, text: str) -> bool:
    normalized = _normalize_text(text)
    if label.startswith("Làm mới"):
        # OCR có thể ghép sai dấu/ký tự đầu, ví dụ "[3mirmơi" và "Miên phi".
        return (
            ("lam" in normalized or "3m" in normalized or "u3m" in normalized)
            and "moi" in normalized
            and "mien" in normalized
            and "phi" in normalized
        )
    return "xacinhan" in normalized or (
        "xac" in normalized and "nhan" in normalized
    )


def recognize_game_options(
    image: Image.Image | np.ndarray | str | Path | None = None,
    *,
    serial: str = "emulator-5554",
    lang: str = "vie+eng",
    tesseract_cmd: str | None = None,
) -> dict[str, Any]:
    """Nhận diện 3 option + 2 button từ ảnh; thiếu ảnh thì tự chụp ADB.

    Kết quả có options (3 phần tử) và buttons (2 phần tử).
    Mỗi phần tử chứa label, text, region, tokens; mỗi token có confidence
    và box với tọa độ tuyệt đối trên toàn màn hình.
    """
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    screen = get_screen_image(image, serial=serial)
    screen_width, screen_height = screen.size
    result: dict[str, Any] = {
        "screen_size": {"width": screen_width, "height": screen_height},
        "options": [],
        "buttons": [],
    }

    for label, left, top, width, height in OPTION_REGIONS:
        right = min(left + width, screen_width)
        bottom = min(top + height, screen_height)
        if left < 0 or top < 0 or left >= right or top >= bottom:
            tokens: list[dict[str, Any]] = []
            actual_width = actual_height = 0
        else:
            crop = screen.crop((left, top, right, bottom))
            tokens = _make_absolute(_read_region(crop, lang=lang, is_button=False), left, top)
            actual_width, actual_height = right - left, bottom - top
        result["options"].append({
            "label": label,
            "region": {"x": left, "y": top, "w": actual_width, "h": actual_height},
            "text": " ".join(token["text"] for token in tokens),
            "tokens": tokens,
        })

    for label, left, top, width, height in BUTTON_REGIONS:
        right = min(left + width, screen_width)
        bottom = min(top + height, screen_height)
        if left < 0 or top < 0 or left >= right or top >= bottom:
            tokens = []
            actual_width = actual_height = 0
        else:
            crop = screen.crop((left, top, right, bottom))
            tokens = _make_absolute(_read_region(crop, lang=lang, is_button=True), left, top)
            actual_width, actual_height = right - left, bottom - top
        text = " ".join(token["text"] for token in tokens)
        result["buttons"].append({
            "label": label,
            "detected": _button_detected(label, text),
            "region": {"x": left, "y": top, "w": actual_width, "h": actual_height},
            "text": text,
            "tokens": tokens,
        })

    return result
