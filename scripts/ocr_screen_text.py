"""OCR the three game options and the two action buttons below Option 1 and 3."""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pytesseract
from adbutils import adb
from PIL import Image, ImageOps
from pytesseract import TesseractNotFoundError

OPTION_REGIONS = (
    ("Option 1", 350, 250, 380, 500),
    ("Option 2", 760, 250, 380, 500),
    ("Option 3", 1160, 250, 400, 500),
)

# Button regions refined from OCR-detected text positions on a 1920x1080 screen.
# Each tuple is (label, left, top, width, height).
BUTTON_REGIONS = (
    ("Làm mới (Miễn Phí)", 400, 820, 500, 180),
    ("Xác Nhận", 1000, 820, 500, 180),
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def ocr_region(crop: Image.Image, lang: str) -> list[tuple[str, float, tuple[int, int, int, int]]]:
    """Return recognized tokens, confidence, and crop-local bounding boxes."""
    scale = 3
    processed = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
    processed = ImageOps.autocontrast(ImageOps.grayscale(processed))
    data = pytesseract.image_to_data(
        processed, lang=lang, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    tokens = []
    for i, raw_text in enumerate(data["text"]):
        text = raw_text.strip()
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if not text or confidence < 20:
            continue
        box = (
            int(data["left"][i] / scale),
            int(data["top"][i] / scale),
            int(data["width"][i] / scale),
            int(data["height"][i] / scale),
        )
        tokens.append((text, confidence, box))
    return tokens


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture and OCR three game options and buttons below Option 1 and Option 3."
    )
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--lang", default="vie+eng", help="Tesseract languages, e.g. vie+eng")
    parser.add_argument("--output", default="screenshots/ocr_screen.png")
    parser.add_argument("--crop-output", default="screenshots/ocr_options.png")
    parser.add_argument("--buttons-output", default="screenshots/ocr_buttons.png")
    parser.add_argument("--tesseract-cmd", help="Path to tesseract.exe if it is not on PATH")
    args = parser.parse_args()

    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

    try:
        device = adb.device(serial=args.serial)
        if device.get_state() != "device":
            print(f"Device {args.serial} is not online.", file=sys.stderr)
            return 1

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        device.screenshot().save(str(output_path))
        print(f"Full screenshot saved: {output_path.resolve()}")
        with Image.open(output_path) as source:
            screenshot = source.convert("RGB")

        screen_width, screen_height = screenshot.size
        print(f"Screen size: {screen_width}x{screen_height}")

        option_crops = []
        for label, x, y, width, height in OPTION_REGIONS:
            right, bottom = min(x + width, screen_width), min(y + height, screen_height)
            if x < 0 or y < 0 or x >= right or y >= bottom:
                print(f"{label} crop is outside screen bounds.", file=sys.stderr)
                return 1
            option_crops.append((label, x, y, screenshot.crop((x, y, right, bottom))))

        gap = 16
        composite = Image.new(
            "RGB",
            (sum(crop.width for _, _, _, crop in option_crops) + gap * 2,
             max(crop.height for _, _, _, crop in option_crops)),
            "white",
        )
        cursor_x = 0
        for _, _, _, crop in option_crops:
            composite.paste(crop, (cursor_x, 0))
            cursor_x += crop.width + gap
        crop_output = Path(args.crop_output)
        crop_output.parent.mkdir(parents=True, exist_ok=True)
        composite.save(crop_output)
        print(f"Image with three option crops saved: {crop_output.resolve()}")

        for label, left, top, crop in option_crops:
            print(f"\n{label}:")
            tokens = ocr_region(crop, args.lang)
            if not tokens:
                print("  No readable text detected in this box.")
            for index, (text, confidence, (x, y, width, height)) in enumerate(tokens, 1):
                print(
                    f"  {index}. {text!r} | box=(x={left + x}, y={top + y}, "
                    f"w={width}, h={height}) | confidence={confidence:.0f}%"
                )

        button_crops = []
        for label, x, y, width, height in BUTTON_REGIONS:
            right, bottom = min(x + width, screen_width), min(y + height, screen_height)
            if x < 0 or y < 0 or x >= right or y >= bottom:
                print(f"{label} crop is outside screen bounds.", file=sys.stderr)
                return 1
            button_crops.append((label, x, y, screenshot.crop((x, y, right, bottom))))

        button_composite = Image.new(
            "RGB",
            (sum(crop.width for _, _, _, crop in button_crops) + gap,
             max(crop.height for _, _, _, crop in button_crops)),
            "white",
        )
        cursor_x = 0
        for _, _, _, crop in button_crops:
            button_composite.paste(crop, (cursor_x, 0))
            cursor_x += crop.width + gap
        buttons_path = Path(args.buttons_output)
        buttons_path.parent.mkdir(parents=True, exist_ok=True)
        button_composite.save(buttons_path)
        print(f"Button crops below Option 1 and Option 3 saved: {buttons_path.resolve()}")

        print("\nButton detection summary:")
        all_detected = True
        for label, left, top, crop in button_crops:
            tokens = ocr_region(crop, args.lang)
            raw_text = " ".join(token[0] for token in tokens)
            normalized = normalize_text(raw_text)
            if label.startswith("Làm mới"):
                detected = all(word in normalized for word in ("lam", "moi", "mien", "phi"))
            else:
                detected = "nhan" in normalized and ("xac" in normalized or "xacinhan" in normalized)
            all_detected = all_detected and detected
            print(f"  {label}: {'DETECTED' if detected else 'NOT CONFIRMED'}")
            print(f"    OCR text: {raw_text or '(none)'}")
            for text, confidence, (x, y, width, height) in tokens:
                print(
                    f"    {text!r} | box=(x={left + x}, y={top + y}, "
                    f"w={width}, h={height}) | confidence={confidence:.0f}%"
                )

        if not all_detected:
            print("If a button is missed, inspect screenshots/ocr_buttons.png and adjust BUTTON_REGIONS.")
        return 0
    except TesseractNotFoundError:
        print("Tesseract not found. Install it or pass --tesseract-cmd.", file=sys.stderr)
        return 1
    except pytesseract.TesseractError as exc:
        print(f"OCR failed: {exc}. Check that language data for {args.lang!r} is installed.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Could not capture or OCR the screen: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
