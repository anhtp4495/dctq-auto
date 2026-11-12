#!/usr/bin/env python3
"""Append one Mưu Binh screenshot row to a transparent vertical image.

Usage:
    python scripts/test_muu_binh_screenshot.py screenshot.png
    python scripts/test_muu_binh_screenshot.py screenshot.png -o preview.png
"""

import argparse
from pathlib import Path

from PIL import Image


def process_image(source: Path, destination: Path, stage_number: int | None) -> int:
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

        existing = None
        if destination.exists():
            existing = Image.open(destination).convert("RGBA")
            if existing.width != 507:
                width = existing.width
                existing.close()
                raise ValueError(f"Ảnh đích rộng {width}px, cần đúng 507px")
            if existing.height > 6900:
                height = existing.height
                existing.close()
                raise ValueError(
                    f"Ảnh đích cao {height}px, vượt quá giới hạn 100 ải (6900px)"
                )
            if existing.height % 69 != 0:
                height = existing.height
                existing.close()
                raise ValueError(
                    f"Chiều cao ảnh đích {height}px không chia hết cho 69px"
                )

        if stage_number is None:
            # Tự tìm hàng trống đầu tiên để không bị nhầm chiều cao cố định 100 ải.
            stage_number = 1
            if existing:
                for index in range(100):
                    top = index * 69
                    if top >= existing.height:
                        stage_number = index + 1
                        break
                    row_alpha = existing.crop((0, top, 507, top + 69)).getchannel("A")
                    if row_alpha.getbbox() is None:
                        stage_number = index + 1
                        break
                else:
                    existing.close()
                    raise ValueError("Đã đủ dữ liệu cả 100 ải")

        if not 1 <= stage_number <= 100:
            if existing:
                existing.close()
            raise ValueError("Số ải phải nằm trong khoảng từ 1 đến 100")

        combined = Image.new("RGBA", (507, 6900), (0, 0, 0, 0))
        if existing:
            combined.paste(existing, (0, 0))
            existing.close()

        # Ải 1 nằm ở hàng đầu tiên; ải 100 nằm ở hàng thứ 100.
        combined.paste(row, (0, (stage_number - 1) * 69))

        destination.parent.mkdir(parents=True, exist_ok=True)
        combined.save(destination, format="PNG")
        return stage_number


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tách chữ trắng và nối mỗi ảnh ải thành một hàng dọc."
    )
    parser.add_argument("image", type=Path, help="Ảnh chụp màn hình gốc")
    parser.add_argument(
        "-a",
        "--stage",
        type=int,
        help="Số ải cần đặt vào đúng hàng (ví dụ: --stage 100)",
    )
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
    if args.stage is not None and not 1 <= args.stage <= 100:
        parser.error("Số ải phải nằm trong khoảng từ 1 đến 100")

    stage_number = process_image(args.image, args.output, args.stage)
    print(
        f"Đã lưu ảnh vào hàng ải {stage_number}: {args.output} "
        f"(507x6900px, đủ 100 ải)"
    )


if __name__ == "__main__":
    main()
