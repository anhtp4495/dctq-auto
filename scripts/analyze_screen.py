"""Mở screenshot, chọn vị trí nút bằng chuột và lưu tọa độ tỷ lệ vào locations.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


DEFAULT_OUTPUT = Path("dctq_auto/tasks/clone/locations.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nhấp vào tâm các nút trên screenshot; nhấn ESC khi đã chọn xong."
    )
    parser.add_argument("--image", required=True, help="Đường dẫn screenshot PNG/JPG")
    parser.add_argument("--screen", required=True, help="Tên trạng thái màn hình, ví dụ login hoặc main")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help=f"File JSON đầu ra (mặc định: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    image_path = Path(args.image)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        print(f"Không đọc được ảnh: {image_path}")
        return 1

    original_height, original_width = image.shape[:2]
    max_width, max_height = 1280, 800
    scale = min(max_width / original_width, max_height / original_height, 1.0)
    display_width = max(1, round(original_width * scale))
    display_height = max(1, round(original_height * scale))
    preview = cv2.resize(image, (display_width, display_height)) if scale < 1.0 else image.copy()
    selected: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        source_x = min(original_width - 1, max(0, round(x / scale)))
        source_y = min(original_height - 1, max(0, round(y / scale)))
        selected.append((source_x, source_y))
        cv2.circle(preview, (x, y), 7, (0, 255, 0), 2)
        cv2.putText(
            preview,
            str(len(selected)),
            (x + 9, y - 9),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(window_name, preview)
        print(
            f"Điểm {len(selected)}: pixel=({source_x}, {source_y}), "
            f"ratio=({source_x / original_width:.5f}, {source_y / original_height:.5f})"
        )

    window_name = f"Analyze screen - {args.screen} | click buttons, ESC to finish"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, on_mouse)
    cv2.imshow(window_name, preview)
    print("Nhấp vào tâm từng nút cần lưu. Nhấn ESC trên cửa sổ ảnh khi hoàn tất.")

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key == 27:
            break
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()

    if not selected:
        print("Chưa chọn điểm nào; không thay đổi file tọa độ.")
        return 0

    entries: dict[str, dict[str, float | int]] = {}
    for index, (x, y) in enumerate(selected, start=1):
        label = input(f"Tên nút cho điểm {index} (ví dụ login_button): ").strip()
        if not label:
            print("Bỏ qua điểm vì tên nút trống.")
            continue
        entries[label] = {
            "x": round(x / original_width, 6),
            "y": round(y / original_height, 6),
            "x_px": x,
            "y_px": y,
        }

    if not entries:
        print("Không có tên nút hợp lệ; không thay đổi file tọa độ.")
        return 0

    output_path = Path(args.output)
    if output_path.exists():
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Không đọc được file tọa độ hiện tại {output_path}: {exc}")
            return 1
    else:
        data = {"screens": {}}

    data.setdefault("reference_resolution", [original_width, original_height])
    data.setdefault("screens", {})
    data["screens"][args.screen] = entries
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã lưu {len(entries)} vị trí cho màn hình {args.screen!r} vào {output_path}")
    print("Lưu ý: tọa độ x/y là tỷ lệ 0..1; x_px/y_px là pixel trên ảnh gốc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
