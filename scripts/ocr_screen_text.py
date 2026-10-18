"""OCR text only inside three approximate game-option boxes."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytesseract
from adbutils import adb
from PIL import Image, ImageOps
from pytesseract import TesseractNotFoundError

# Approximate screen coordinates: (label, x, y, width, height).
# Adjust these values if the three cards are elsewhere on your screen.
OPTION_REGIONS = (
    ("Option 1", 350, 250, 380, 500),
    ("Option 2", 760, 250, 380, 500),
    ("Option 3", 1160, 250, 400, 500),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the screen and OCR only the three game-option boxes."
    )
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--lang", default="eng", help="Use vie+eng for Vietnamese and English")
    parser.add_argument("--output", default="screenshots/ocr_screen.png")
    parser.add_argument("--crop-output", default="screenshots/ocr_options.png")
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
        crops = []
        for label, x, y, width, height in OPTION_REGIONS:
            right = min(x + width, screen_width)
            bottom = min(y + height, screen_height)
            if x < 0 or y < 0 or x >= right or y >= bottom:
                print(f"{label} crop is outside screen bounds {screen_width}x{screen_height}.", file=sys.stderr)
                return 1
            crops.append((label, x, y, screenshot.crop((x, y, right, bottom))))

        gap = 16
        composite = Image.new(
            "RGB",
            (sum(crop.width for _, _, _, crop in crops) + gap * 2,
             max(crop.height for _, _, _, crop in crops)),
            "white",
        )
        cursor_x = 0
        for _, _, _, crop in crops:
            composite.paste(crop, (cursor_x, 0))
            cursor_x += crop.width + gap
        crop_output = Path(args.crop_output)
        crop_output.parent.mkdir(parents=True, exist_ok=True)
        composite.save(crop_output)
        print(f"Image with only the three cropped boxes saved: {crop_output.resolve()}")
        print(f"Screen size: {screen_width}x{screen_height}")

        total = 0
        for label, left, top, crop in crops:
            scale = 2
            processed = crop.resize(
                (crop.width * scale, crop.height * scale),
                Image.Resampling.LANCZOS,
            )
            processed = ImageOps.autocontrast(ImageOps.grayscale(processed))
            data = pytesseract.image_to_data(
                processed,
                lang=args.lang,
                config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
            print(f"\n{label}:")
            count = 0
            for i, raw_text in enumerate(data["text"]):
                text = raw_text.strip()
                try:
                    confidence = float(data["conf"][i])
                except (TypeError, ValueError):
                    continue
                if not text or confidence < 25:
                    continue
                x = left + int(data["left"][i] / scale)
                y = top + int(data["top"][i] / scale)
                width = int(data["width"][i] / scale)
                height = int(data["height"][i] / scale)
                count += 1
                total += 1
                print(
                    f"  {count}. {text!r} | box=(x={x}, y={y}, "
                    f"w={width}, h={height}) | confidence={confidence:.0f}%"
                )
            if count == 0:
                print("  No readable text detected in this box.")

        if total == 0:
            print("No text found. Open the cropped image and adjust OPTION_REGIONS.")
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
