#!/usr/bin/env python3
"""Append one Mưu Binh screenshot row to a transparent vertical image.

Usage:
    python scripts/test_muu_binh_screenshot.py screenshot.png
    python scripts/test_muu_binh_screenshot.py screenshot.png -o preview.png
"""

import argparse
from pathlib import Path

from PIL import Image


def process_image(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        if image.width < 1214 or image.height < 86:
            raise ValueError(
                f"Ảnh phải có kích thước tối thiểu 1214x86, hiện tại "
                f"{image.width}x{image.height}"
            )

        row = image.crop((707, 17, 1214, 86)).convert("RGBA")
        result = []

        for red, green, blue, _alpha in row.getdata():
            darkest = min(red, green, blue)
            brightest = max(red, green, blue)
            if darkest >= 180 and brightest - darkest <= 60:
                alpha = min(255, max(0, int((darkest - 160) * 255 / 95)))
                result.append((255, 255, 255, alpha))
            else:
                result.append((0, 0, 0, 0))

        row.putdata(result)

        if destination.exists():
            existing = Image.open(destination).convert("RGBA")
            if existing.width != 507:
                existing.close()
                raise ValueError(
                    f"Ảnh đích rộng {existing.width}px, cần đúng 507px"
                )
            combined = Image.new(
                "RGBA", (507, existing.height + 69), (0, 0, 0, 0)
            )
            combined.paste(existing, (0, 0))
            combined.paste(row, (0, existing.height))
            existing.close()
        else:
            combined = row

        destination.parent.mkdir(parents=True, exist_ok=True)
        combined.save(destination, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tách chữ trắng và nối mỗi ảnh ải thành một hàng dọc."
    )
    parser.add_argument("image", type=Path, help="Ảnh chụp màn hình gốc")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("danh_sach_ai.png"),
        help="File PNG danh sách (mặc định: danh_sach_ai.png)",
    )
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Không tìm thấy ảnh: {args.image}")

    process_image(args.image, args.output)
    print(f"Đã thêm một hàng vào: {args.output}")


if __name__ == "__main__":
    main()
