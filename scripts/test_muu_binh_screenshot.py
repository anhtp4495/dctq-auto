#!/usr/bin/env python3
"""Append one Mưu Binh screenshot row to a transparent vertical image.

Usage:
    python scripts/test_muu_binh_screenshot.py screenshot.png
    python scripts/test_muu_binh_screenshot.py screenshot.png -o preview.png
"""

import argparse
from pathlib import Path

from PIL import Image


# Đồng bộ với _STAGE_SCREENSHOT_RECT trong task_run_stage_defense.py.
_STAGE_SCREENSHOT_RECT = (670, 20, 1250, 80)
_STAGE_IMAGE_WIDTH = _STAGE_SCREENSHOT_RECT[2] - _STAGE_SCREENSHOT_RECT[0]
_STAGE_IMAGE_HEIGHT = _STAGE_SCREENSHOT_RECT[3] - _STAGE_SCREENSHOT_RECT[1]
_STAGE_IMAGE_COUNT = 100
_STAGE_CANVAS_HEIGHT = _STAGE_IMAGE_HEIGHT * _STAGE_IMAGE_COUNT


def process_image(source: Path, destination: Path, stage_number: int | None) -> tuple[int, int]:
    with Image.open(source) as image:
        if image.width < _STAGE_SCREENSHOT_RECT[2] or image.height < _STAGE_SCREENSHOT_RECT[3]:
            raise ValueError(
                f"Ảnh phải có kích thước tối thiểu {_STAGE_SCREENSHOT_RECT[2]}x{_STAGE_SCREENSHOT_RECT[3]}, hiện tại "
                f"{image.width}x{image.height}"
            )

        row = image.crop(_STAGE_SCREENSHOT_RECT).convert("RGBA")
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

        # Bỏ qua pixel trắng lẻ/nhạt để tránh xác định nhầm mép trái.
        solid_alpha = row.getchannel("A").point(
            lambda value: 255 if value >= 128 else 0
        )
        alpha_bbox = solid_alpha.getbbox()
        left_offset = alpha_bbox[0] if alpha_bbox else 0

        if left_offset:
            # Cắt phần lề trái rồi đặt nội dung vào canvas mới cùng kích thước.
            # Cách này giữ nguyên chiều ngang 580px và không làm mất chữ do
            # paste với tọa độ âm.
            aligned_row = Image.new(
                "RGBA", (_STAGE_IMAGE_WIDTH, _STAGE_IMAGE_HEIGHT), (0, 0, 0, 0)
            )
            content = row.crop(
                (left_offset, 0, _STAGE_IMAGE_WIDTH, _STAGE_IMAGE_HEIGHT)
            )
            aligned_row.paste(content, (0, 0))
            row = aligned_row

        existing = None
        if destination.exists():
            existing = Image.open(destination).convert("RGBA")
            if existing.width != _STAGE_IMAGE_WIDTH:
                width = existing.width
                existing.close()
                raise ValueError(f"Ảnh đích rộng {width}px, cần đúng {_STAGE_IMAGE_WIDTH}px")
            if existing.height > _STAGE_CANVAS_HEIGHT:
                height = existing.height
                existing.close()
                raise ValueError(
                    f"Ảnh đích cao {height}px, vượt quá giới hạn 100 ải ({_STAGE_CANVAS_HEIGHT}px)"
                )
            if existing.height % _STAGE_IMAGE_HEIGHT != 0:
                height = existing.height
                existing.close()
                raise ValueError(
                    f"Chiều cao ảnh đích {height}px không chia hết cho {_STAGE_IMAGE_HEIGHT}px"
                )

        if stage_number is None:
            # Tự tìm hàng trống đầu tiên để không bị nhầm chiều cao cố định 100 ải.
            stage_number = 1
            if existing:
                for index in range(_STAGE_IMAGE_COUNT):
                    top = index * _STAGE_IMAGE_HEIGHT
                    if top >= existing.height:
                        stage_number = index + 1
                        break
                    row_alpha = existing.crop((0, top, _STAGE_IMAGE_WIDTH, top + _STAGE_IMAGE_HEIGHT)).getchannel("A")
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

        combined = Image.new("RGBA", (_STAGE_IMAGE_WIDTH, _STAGE_CANVAS_HEIGHT), (0, 0, 0, 0))
        if existing:
            combined.paste(existing, (10, 0))
            existing.close()

        # Ải 1 nằm ở hàng đầu tiên; ải 100 nằm ở hàng thứ 100.
        combined.paste(row, (0, (stage_number - 1) * _STAGE_IMAGE_HEIGHT))

        destination.parent.mkdir(parents=True, exist_ok=True)
        combined.save(destination, format="PNG")
        return stage_number, left_offset


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

    stage_number, left_offset = process_image(args.image, args.output, args.stage)
    print(
        f"Đã lưu ảnh vào hàng ải {stage_number}: {args.output} "
        f"({_STAGE_IMAGE_WIDTH}x{_STAGE_CANVAS_HEIGHT}px, đủ {_STAGE_IMAGE_COUNT} ải)"
    )
    print(f"Đã dịch chữ sang trái: {left_offset}px")


if __name__ == "__main__":
    main()
