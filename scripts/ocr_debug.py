#!/usr/bin/env python3
"""Interactive Tesseract OCR debugger for game screenshots.

Examples:
  python scripts/ocr_debug.py
  python scripts/ocr_debug.py screenshot.png
  python scripts/ocr_debug.py screenshot.png --rect 201 726 474 871
  python scripts/ocr_debug.py screenshot.png --lang vie --psm 7
  python scripts/ocr_debug.py screenshot.png --tesseract-cmd "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

When no image path is supplied, a file picker opens. Without --rect, drag a rectangle
around the text in the preview and press Enter/Space. Press C to cancel ROI selection
and OCR the whole image.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path
from tkinter import Tk, filedialog

import cv2
import numpy as np
import pytesseract
from pytesseract import Output


def choose_image() -> Path | None:
    root = Tk()
    root.withdraw()
    try:
        filename = filedialog.askopenfilename(
            title="Chọn ảnh screenshot để debug OCR",
            filetypes=[
                ("Ảnh", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("Tất cả file", "*.*"),
            ],
        )
    finally:
        root.destroy()
    return Path(filename) if filename else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug OCR Tesseract: chọn RECT, thử tiền xử lý và PSM, lưu kết quả."
    )
    parser.add_argument("image", nargs="?", help="Đường dẫn ảnh; bỏ trống để mở hộp thoại chọn ảnh.")
    parser.add_argument(
        "--rect", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help="RECT theo pixel ảnh gốc, dạng: left top right bottom.",
    )
    parser.add_argument("--lang", default="vie+eng", help="Ngôn ngữ Tesseract (mặc định: vie+eng).")
    parser.add_argument(
        "--psm", nargs="+", type=int, choices=range(14), default=[6, 7, 11],
        help="Các PSM cần thử (mặc định: 6 7 11).",
    )
    parser.add_argument("--scale", type=int, default=3, help="Hệ số phóng to (mặc định: 3).")
    parser.add_argument(
        "--steps", nargs="+",
        choices=("gray", "clahe", "otsu", "otsu_inverted"),
        default=["gray", "clahe", "otsu", "otsu_inverted"],
        help="Chỉ chạy các bước được chọn (mặc định: gray clahe otsu otsu_inverted).",
    )
    parser.add_argument(
        "--tesseract-cmd", help="Đường dẫn tesseract.exe nếu không có trong PATH."
    )
    parser.add_argument("--output", help="Thư mục lưu kết quả; mặc định: ocr_debug_<tên ảnh> cạnh ảnh.")
    return parser.parse_args()


def select_rect(image: np.ndarray) -> tuple[int, int, int, int] | None:
    preview = image.copy()
    h, w = preview.shape[:2]
    # Shrink only the preview if it is too large; ROI coordinates are scaled back.
    max_width, max_height = 1400, 850
    factor = min(max_width / w, max_height / h, 1.0)
    if factor < 1:
        preview = cv2.resize(
            preview, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_AREA
        )
    print("Kéo chuột chọn RECT quanh chữ, nhấn ENTER/SPACE để xác nhận, C để bỏ chọn.")
    x, y, rw, rh = cv2.selectROI("Chon RECT OCR - ENTER/SPACE de xac nhan", preview, False, False)
    cv2.destroyWindow("Chon RECT OCR - ENTER/SPACE de xac nhan")
    if rw <= 0 or rh <= 0:
        return None
    left = max(0, int(round(x / factor)))
    top = max(0, int(round(y / factor)))
    right = min(w, int(round((x + rw) / factor)))
    bottom = min(h, int(round((y + rh) / factor)))
    return left, top, right, bottom


def preprocess(crop: np.ndarray, scale: int, steps: list[str]) -> dict[str, np.ndarray]:
    # Each stage is derived from the previous stage so the user can inspect the
    # image transformation step by step. gray includes optional upscale/padding.
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if scale > 1:
        gray = cv2.resize(
            gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4
        )
    gray = cv2.copyMakeBorder(gray, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255)

    variants: dict[str, np.ndarray] = {}
    if "gray" in steps:
        variants["gray"] = gray

    # Later operations still use the intermediate result even if it isn't
    # selected for saving. This keeps the pipeline consistent.
    contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if "clahe" in steps:
        variants["clahe"] = contrast

    _, otsu = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if "otsu" in steps:
        variants["otsu"] = otsu

    _, otsu_inv = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if "otsu_inverted" in steps:
        variants["otsu_inverted"] = otsu_inv

    return variants


def main() -> int:
    args = parse_args()
    image_path = Path(args.image).expanduser() if args.image else choose_image()
    if not image_path:
        print("Chưa chọn ảnh.")
        return 1
    if not image_path.is_file():
        print(f"Không tìm thấy ảnh: {image_path}")
        return 1
    if args.scale < 1:
        print("--scale phải >= 1.")
        return 2
    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd
    elif shutil.which("tesseract") is None:
        common = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if common.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(common)
        else:
            print("Không tìm thấy tesseract.exe trong PATH. Dùng --tesseract-cmd để chỉ định đường dẫn.")
            return 2

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        print(f"OpenCV không đọc được ảnh: {image_path}")
        return 1
    image_h, image_w = image.shape[:2]

    if args.rect:
        left, top, right, bottom = args.rect
    else:
        selected = select_rect(image)
        if selected is None:
            left, top, right, bottom = 0, 0, image_w, image_h
            print("Không chọn RECT; sẽ OCR toàn bộ ảnh.")
        else:
            left, top, right, bottom = selected

    left, right = sorted((max(0, left), min(image_w, right)))
    top, bottom = sorted((max(0, top), min(image_h, bottom)))
    if right <= left or bottom <= top:
        print(f"RECT không hợp lệ: ({left}, {top}, {right}, {bottom})")
        return 2

    crop = image[top:bottom, left:right]
    output_dir = Path(args.output) if args.output else image_path.parent / f"ocr_debug_{image_path.stem}"
    output_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_dir / "00_original_crop.png"), crop)
    variants = preprocess(crop, args.scale, args.steps)

    try:
        installed = set(pytesseract.get_languages(config=""))
    except pytesseract.TesseractNotFoundError:
        print("Không chạy được Tesseract. Kiểm tra --tesseract-cmd hoặc cài Tesseract OCR.")
        return 2
    requested = args.lang.split("+")
    missing = [lang for lang in requested if lang not in installed]
    if missing:
        print(f"CẢNH BÁO: thiếu language data: {', '.join(missing)}")
        print("Ngôn ngữ đang cài:", ", ".join(sorted(installed)))

    print(f"\nẢnh: {image_path}")
    print(f"Kích thước ảnh gốc: {image_w}x{image_h}")
    print(f"RECT: ({left}, {top}, {right}, {bottom})")
    print(f"Kích thước RECT: {right-left}x{bottom-top}; scale={args.scale}; lang={args.lang}")
    print(f"Các bước được chọn: {', '.join(args.steps)}")
    print(f"Kết quả sẽ lưu tại: {output_dir.resolve()}")
    summary_path = output_dir / "results.txt"
    with summary_path.open("w", encoding="utf-8") as summary:
        summary.write(f"Image: {image_path}\nRECT: ({left}, {top}, {right}, {bottom})\n")
        summary.write(f"Language: {args.lang}; scale: {args.scale}; PSM: {args.psm}\n")

        for variant_name, processed in variants.items():
            # Keep filenames tied to the source image name, with the selected
            # processing stage as suffix (e.g. screenshot.gray.png).
            processed_path = output_dir / f"{image_path.stem}.{variant_name}.png"
            cv2.imwrite(str(processed_path), processed)
            for psm in args.psm:
                config = f"--oem 3 --psm {psm}"
                try:
                    data = pytesseract.image_to_data(
                        processed, lang=args.lang, config=config, output_type=Output.DICT
                    )
                except pytesseract.TesseractError as exc:
                    message = f"[{variant_name} | PSM {psm}] LỖI: {exc}"
                    print(message)
                    summary.write(message + "\n\n")
                    continue

                words = []
                confidences = []
                for i, raw_text in enumerate(data["text"]):
                    word = raw_text.strip()
                    try:
                        conf = float(data["conf"][i])
                    except (ValueError, TypeError):
                        conf = -1
                    if word and conf >= 0:
                        words.append(word)
                        confidences.append(conf)
                recognized = " ".join(words)
                avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                header = f"[{variant_name} | PSM {psm}] confidence trung bình: {avg_conf:.1f}"
                print(f"\n{header}\n{recognized or '(không nhận diện được chữ)'}")
                summary.write(header + "\n" + (recognized or "(không nhận diện được chữ)") + "\n\n")

                csv_path = output_dir / f"{image_path.stem}.{variant_name}.psm{psm}.csv"
                with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow([
                        "text", "confidence", "left_processed", "top_processed",
                        "width_processed", "height_processed",
                    ])
                    for i, raw_text in enumerate(data["text"]):
                        word = raw_text.strip()
                        if not word:
                            continue
                        writer.writerow([
                            word, data["conf"][i], data["left"][i], data["top"][i],
                            data["width"][i], data["height"][i],
                        ])

                # Draw word boxes on the processed crop for visual inspection.
                annotated = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                for i, raw_text in enumerate(data["text"]):
                    if not raw_text.strip():
                        continue
                    x, y = int(data["left"][i]), int(data["top"][i])
                    w, h = int(data["width"][i]), int(data["height"][i])
                    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 180, 0), 1)
                cv2.imwrite(str(output_dir / f"{image_path.stem}.{variant_name}.psm{psm}.boxes.png"), annotated)

    print(f"\nHoàn tất. Mở {output_dir.resolve()} để so sánh ảnh xử lý, kết quả và bounding boxes.")
    print(f"File tổng hợp: {summary_path.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nĐã hủy.")
        raise SystemExit(130)
