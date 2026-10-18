"""Capture an Android screenshot and OCR visible text with Tesseract.

Run from the repository root:
    py -m pip install -r requirements.txt
    # Install the Tesseract OCR application separately on Windows.
    py scripts/ocr_screen_text.py --serial emulator-5554 --lang eng

For Vietnamese and English text, use --lang vie+eng after installing the
Vietnamese Tesseract language data. Detected bounding boxes are printed as
(x, y, width, height), measured from the screenshot's top-left corner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import pytesseract
from adbutils import adb
from pytesseract import TesseractNotFoundError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Take a screenshot from an Android device and OCR its text."
    )
    parser.add_argument(
        "--serial",
        default="emulator-5554",
        help="ADB device serial (default: emulator-5554)",
    )
    parser.add_argument(
        "--lang",
        default="eng",
        help="Tesseract language(s), e.g. eng or vie+eng (default: eng)",
    )
    parser.add_argument(
        "--output",
        default="screenshots/ocr_screen.png",
        help="Screenshot output path (default: screenshots/ocr_screen.png)",
    )
    parser.add_argument(
        "--tesseract-cmd",
        help="Optional full path to tesseract.exe if it is not on PATH",
    )
    args = parser.parse_args()

    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

    try:
        device = adb.device(serial=args.serial)
        state = device.get_state()
        if state != "device":
            print(f"Device {args.serial} is not online (state: {state}).", file=sys.stderr)
            return 1

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        device.screenshot().save(str(output_path))
        print(f"Screenshot saved: {output_path.resolve()}")

        image = cv2.imread(str(output_path))
        if image is None:
            print("Could not open the captured screenshot with OpenCV.", file=sys.stderr)
            return 1

        # Enlarge small game text to improve OCR accuracy.
        height, width = image.shape[:2]
        scale = 2 if max(width, height) < 1800 else 1
        if scale > 1:
            image = cv2.resize(
                image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        data = pytesseract.image_to_data(
            gray,
            lang=args.lang,
            config="--psm 11",
            output_type=pytesseract.Output.DICT,
        )

        print("\nOCR results:")
        found = 0
        for i, raw_text in enumerate(data["text"]):
            text = raw_text.strip()
            try:
                confidence = float(data["conf"][i])
            except (TypeError, ValueError):
                continue

            if not text or confidence < 25:
                continue

            x = int(data["left"][i] / scale)
            y = int(data["top"][i] / scale)
            box_width = int(data["width"][i] / scale)
            box_height = int(data["height"][i] / scale)
            found += 1
            print(
                f"{found}. {text!r} | box=(x={x}, y={y}, "
                f"w={box_width}, h={box_height}) | confidence={confidence:.0f}%"
            )

        if not found:
            print("No readable text detected.")
            print(
                "Check that the correct screen is open, try --lang vie+eng, "
                "or inspect the saved screenshot."
            )
        return 0

    except TesseractNotFoundError:
        print(
            "Tesseract executable not found. Install Tesseract OCR and add it "
            "to PATH, or pass --tesseract-cmd with the path to tesseract.exe.",
            file=sys.stderr,
        )
        return 1
    except pytesseract.TesseractError as exc:
        print(
            f"Tesseract OCR failed: {exc}. Check that language data for "
            f"{args.lang!r} is installed.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Could not capture or OCR the screen: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
