"""Chụp màn hình thiết bị Android/LDPlayer qua ADB để phân tích thủ công."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from adbutils import adb


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chụp màn hình ADB và lưu ảnh để dùng với scripts/analyze_screen.py."
    )
    parser.add_argument("--serial", default="emulator-5554", help="ADB serial, ví dụ emulator-5554 hoặc 127.0.0.1:5555")
    parser.add_argument("--output", help="Đường dẫn file ảnh đầu ra (mặc định: artifacts/screenshots/<serial>_<timestamp>.png)")
    args = parser.parse_args()

    try:
        device = adb.device(serial=args.serial)
        device.get_state()
        if args.output:
            output_path = Path(args.output)
        else:
            safe_serial = args.serial.replace(":", "_").replace("/", "_").replace("\\\\", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path("artifacts") / "screenshots" / f"{safe_serial}_{timestamp}.png"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        device.screenshot().save(str(output_path))
        print(f"Đã lưu screenshot: {output_path.resolve()}")
        return 0
    except Exception as exc:
        print(f"Không thể chụp màn hình thiết bị {args.serial!r}: {exc}")
        print("Kiểm tra LDPlayer đang chạy và thiết bị xuất hiện trong lệnh adb devices.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
