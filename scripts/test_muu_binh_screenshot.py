#!/usr/bin/env python3
"""Crop the Mưu Binh status strip and keep only white text on transparency.

Usage:
    python scripts/test_muu_binh_screenshot.py screenshot.png
    python scripts/test_muu_binh_screenshot.py screenshot.png -o preview.png
"""

import argparse
from pathlib import Path

from PIL import Image


def process_image(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        if image.width < 1219 or image.height < 96:
            raise ValueError(
                f"Ảnh phải có kích thước tối thiểu 1219x96, hiện tại "
                f"{image.width}x{image.height}"
            )

        cropped = image.crop((710, 0, 1219, 96)).convert("RGBA")
        result = []

        for red, green, blue, _alpha in cropped.getdata():
            darkest = min(red, green, blue)
            brightest = max(red, green, blue)

            # Chỉ nhận màu gần trắng, loại các pixel có sắc độ rõ rệt.
            if darkest >= 180 and brightest - darkest <= 60:
                alpha = min(255, max(0, int((darkest - 160) * 255 / 95)))
                result.append((255, 255, 255, alpha))
            else:
                result.append((0, 0, 0, 0))

        cropped.putdata(result)
        destination.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(destination, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tách chữ trắng khỏi ảnh Mưu Binh, nền kết quả trong suốt."
    )
    parser.add_argument("image", type=Path, help="Đường dẫn ảnh chụp màn hình gốc")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Ảnh PNG đầu ra (mặc định: <tên ảnh gốc>_white_text.png)",
    )
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Không tìm thấy ảnh: {args.image}")

    output = args.output or args.image.with_name(
        f"{args.image.stem}_white_text.png"
    )
    process_image(args.image, output)
    print(f"Đã lưu ảnh kết quả: {output}")


if __name__ == "__main__":
    main()
