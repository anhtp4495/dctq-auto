#!/usr/bin/env python3
"""OCR preprocessing / noise-cleaning debugger for game screenshots.

Creates inspectable image variants (denoising, contrast enhancement, thresholding,
and optional diagonal-line suppression), runs Tesseract on each variant, and
writes images plus OCR results to an output folder.

Examples:
    python scripts/ocr_cleaning_debug.py resources/screens/muu_binh/ai_31.png
    python scripts/ocr_cleaning_debug.py screenshot.png --psm 6 7 8 11 13
    python scripts/ocr_cleaning_debug.py screenshot.png --remove-lines
    python scripts/ocr_cleaning_debug.py screenshot.png --whitelist "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from tkinter import Tk, filedialog

import cv2
import numpy as np
import pytesseract


def choose_image() -> Path | None:
    root = Tk()
    root.withdraw()
    try:
        filename = filedialog.askopenfilename(
            title="Chọn ảnh để debug làm sạch OCR",
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
        description="Thử nhiều cách xử lý nhiễu ảnh và so sánh kết quả OCR."
    )
    parser.add_argument("image", nargs="?", help="Đường dẫn ảnh; bỏ trống để mở hộp thoại chọn ảnh.")
    parser.add_argument("--lang", default="vie+eng", help="Ngôn ngữ Tesseract (mặc định: vie+eng).")
    parser.add_argument(
        "--psm", nargs="+", type=int, choices=range(14), default=[6, 7, 8, 11, 13],
        help="Các PSM thử cho từng ảnh (mặc định: 6 7 8 11 13).",
    )
    parser.add_argument("--scale", type=int, default=4, help="Hệ số phóng to (mặc định: 4).")
    parser.add_argument(
        "--remove-lines", action="store_true",
        help="Thử phát hiện và loại các nét thẳng/chéo bằng morphology + inpainting.",
    )
    parser.add_argument(
        "--whitelist", 
        default="", 
        help="Giới hạn ký tự cho phép (ví dụ: '0123456789' hoặc 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')."
    )
    parser.add_argument("--tesseract-cmd", help="Đường dẫn tesseract.exe nếu không có trong PATH.")
    parser.add_argument("--output", help="Thư mục lưu ảnh xử lý và results.txt.")
    return parser.parse_args()


def remove_straight_lines(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Attempt to remove long straight strokes while retaining nearby text.

    Optimized to catch bright diagonal lines crossing text (like in game UIs).
    """
    height, width = gray.shape[:2]
    min_length = max(8, min(height, width) // 6)

    # Detect bright lines (since the diagonal stripe in the sample is white/bright)
    # Using thresholding + morphological operations to isolate bright lines
    _, bright_thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, width // 4), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, height // 4)))
    horizontal = cv2.morphologyEx(bright_thresh, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(bright_thresh, cv2.MORPH_OPEN, vertical_kernel)

    # HoughLinesP on Canny edges to find diagonal lines precisely
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=max(10, min_length // 2),
        minLineLength=min_length, maxLineGap=10,
    )
    
    diagonal_mask = np.zeros_like(gray)
    if lines is not None:
        for segment in np.asarray(lines).reshape(-1, 4):
            x1, y1, x2, y2 = (int(value) for value in segment)
            length = float(np.hypot(x2 - x1, y2 - y1))
            if length < min_length:
                continue
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            # Target diagonal lines (e.g., between 15 and 165 degrees)
            if 10 <= angle <= 170:
                cv2.line(diagonal_mask, (x1, y1), (x2, y2), 255, max(3, width // 30))

    line_mask = cv2.bitwise_or(horizontal, vertical)
    line_mask = cv2.bitwise_or(line_mask, diagonal_mask)
    line_mask = cv2.dilate(line_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    
    # Inpaint using the surrounding background texture
    cleaned = cv2.inpaint(gray, line_mask, 3, cv2.INPAINT_TELEA)
    return cleaned, line_mask


def make_variants(crop: np.ndarray, scale: int, try_remove_lines: bool) -> dict[str, np.ndarray]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if scale > 1:
        gray = cv2.resize(
            gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
        )

    variants: dict[str, np.ndarray] = {"01_gray_scaled": gray}

    # Common denoising methods
    median = cv2.medianBlur(gray, 3 if min(gray.shape[:2]) >= 3 else 1)
    variants["02_median_denoise"] = median

    bilateral = cv2.bilateralFilter(gray, 7, 50, 50)
    variants["03_bilateral_denoise"] = bilateral

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    variants["04_clahe_contrast"] = clahe

    blur = cv2.GaussianBlur(clahe, (3, 3), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["05_otsu"] = otsu

    _, otsu_inv = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    variants["06_otsu_inverted"] = otsu_inv

    adaptive = cv2.adaptiveThreshold(
        clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    variants["07_adaptive_threshold"] = adaptive

    # Morphological cleaning variant
    binary_inv = cv2.bitwise_not(otsu)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    opened = cv2.morphologyEx(binary_inv, cv2.MORPH_OPEN, kernel)
    variants["08_morphology_denoise"] = cv2.bitwise_not(opened)

    if try_remove_lines:
        cleaned, mask = remove_straight_lines(gray)
        variants["09_line_removal_mask"] = mask
        variants["10_line_removed_gray"] = cleaned
        cleaned_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(cleaned)
        _, cleaned_otsu = cv2.threshold(
            cv2.GaussianBlur(cleaned_clahe, (3, 3), 0),
            0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        variants["11_line_removed_otsu"] = cleaned_otsu

    # Add a white quiet-zone border to OCR inputs to reduce edge clipping.
    return {
        name: cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        for name, img in variants.items()
    }


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
            print("Không tìm thấy Tesseract trong PATH; dùng --tesseract-cmd để chỉ định đường dẫn.")
            return 2

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        print(f"OpenCV không đọc được ảnh: {image_path}")
        return 1
    image_h, image_w = image.shape[:2]

    left, top, right, bottom = 0, 0, image_w, image_h
    output_dir = (
        Path(args.output).expanduser()
        if args.output else image_path.parent / f"ocr_cleaning_{image_path.stem}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_dir / "00_original_image.png"), image)

    try:
        installed = set(pytesseract.get_languages(config=""))
    except pytesseract.TesseractNotFoundError:
        print("Không chạy được Tesseract. Kiểm tra --tesseract-cmd hoặc cài Tesseract OCR.")
        return 2
    
    missing = [lang for lang in args.lang.split("+") if lang not in installed]
    if missing:
        print(f"CẢNH BÁO: thiếu language data: {', '.join(missing)}")
        print("Ngôn ngữ hiện có:", ", ".join(sorted(installed)))

    variants = make_variants(image, args.scale, args.remove_lines)
    
    # Configure Tesseract options
    config_options = " -c preserve_interword_spaces=1"
    if args.whitelist:
        config_options += f" -c tessedit_char_whitelist={args.whitelist}"

    results: list[str] = [
        f"Image: {image_path}",
        f"Image size: {image_w}x{image_h}",
        f"RECT: ({left}, {top}, {right}, {bottom})",
        f"Scale: {args.scale}; language: {args.lang}; PSM: {args.psm}",
        f"Remove lines enabled: {args.remove_lines}",
        f"Whitelist: {args.whitelist or 'None'}",
        "",
    ]

    print(f"Ảnh: {image_path}")
    print(f"Xử lý toàn ảnh: {image_w}x{image_h}; scale={args.scale}; lang={args.lang}")
    print(f"Lưu ảnh và kết quả tại: {output_dir.resolve()}")
    
    for name, processed in variants.items():
        image_file = output_dir / f"{name}.png"
        cv2.imwrite(str(image_file), processed)
        results.append(f"===== {name} =====")
        for psm in args.psm:
            config = f"--oem 3 --psm {psm}{config_options}"
            try:
                text = pytesseract.image_to_string(processed, lang=args.lang, config=config)
                normalized = " ".join(text.split())
            except pytesseract.TesseractError as exc:
                normalized = f"[Tesseract error: {exc}]"
            line = f"PSM {psm}: {normalized or '[không nhận diện được chữ]'}"
            results.append(line)
            print(f"{name} | {line}")
        results.append("")

    summary_path = output_dir / "results.txt"
    summary_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    print(f"Đã ghi tổng hợp OCR: {summary_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())