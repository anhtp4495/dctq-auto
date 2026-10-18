"""CLI kiểm thử hàm OCR dùng chung trong dctq_auto.tasks.game_options."""
from __future__ import annotations

import argparse
import json
import sys

import pytesseract
from pytesseract import TesseractNotFoundError

from dctq_auto.tasks.game_options import recognize_game_options


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nhận diện 3 option và 2 button, kèm tọa độ trên màn hình."
    )
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--lang", default="vie+eng")
    parser.add_argument("--image", help="Đường dẫn ảnh có sẵn; bỏ qua để chụp qua ADB")
    parser.add_argument("--tesseract-cmd", help="Đường dẫn tesseract.exe nếu chưa có trong PATH")
    args = parser.parse_args()

    try:
        result = recognize_game_options(
            image=args.image,
            serial=args.serial,
            lang=args.lang,
            tesseract_cmd=args.tesseract_cmd,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except TesseractNotFoundError:
        print("Không tìm thấy Tesseract. Cài đặt hoặc truyền --tesseract-cmd.", file=sys.stderr)
        return 1
    except pytesseract.TesseractError as exc:
        print(f"OCR thất bại: {exc}. Kiểm tra dữ liệu ngôn ngữ {args.lang!r}.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Không thể chụp hoặc nhận diện màn hình: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
