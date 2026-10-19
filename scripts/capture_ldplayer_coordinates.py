"""Ghi tọa độ chuột trên LDPlayer và chọn vùng 4 góc để phân tích ảnh.

Windows-only. F8 ghi một điểm; F9 bật chế độ ghi 4 góc bằng F8 theo thứ tự:
trên-trái, trên-phải, dưới-phải, dưới-trái. ESC hủy chọn hoặc thoát.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from adbutils import adb
    from pynput import keyboard
except ImportError as exc:
    print(f"Thiếu thư viện: {exc}. Hãy cài bằng .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    raise SystemExit(1)

if sys.platform != "win32":
    raise SystemExit("Công cụ này hiện chỉ hỗ trợ Windows.")

DEFAULT_OUTPUT = Path("dctq_auto/tasks/clone/regions.json")
LOG_PATH = Path("artifacts/coordinate_capture.log")
user32 = ctypes.windll.user32


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    top_left = ctypes.wintypes.POINT(rect.left, rect.top)
    bottom_right = ctypes.wintypes.POINT(rect.right, rect.bottom)
    user32.ClientToScreen(hwnd, ctypes.byref(top_left))
    user32.ClientToScreen(hwnd, ctypes.byref(bottom_right))
    width = bottom_right.x - top_left.x
    height = bottom_right.y - top_left.y
    if width <= 0 or height <= 0:
        return None
    return top_left.x, top_left.y, width, height


def find_ldplayer_window(title_hint: str) -> tuple[int, str, tuple[int, int, int, int]]:
    matches: list[tuple[int, str, tuple[int, int, int, int]]] = []
    enum_callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @enum_callback_type
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title_hint.casefold() not in title.casefold():
            return True
        rect = get_window_rect(hwnd)
        if rect:
            matches.append((int(hwnd), title, rect))
        return True

    user32.EnumWindows(callback, 0)
    if not matches:
        raise RuntimeError(
            f"Không tìm thấy cửa sổ có tiêu đề chứa {title_hint!r}. "
            "Hãy mở LDPlayer hoặc chạy lại với --window-title."
        )
    # Prefer the largest matching visible window.
    return max(matches, key=lambda item: item[2][2] * item[2][3])


def load_device_resolution(serial: str) -> tuple[int, int]:
    device = adb.device(serial=serial)
    device.get_state()
    screenshot = device.screenshot()
    width, height = screenshot.size
    if width <= 0 or height <= 0:
        raise RuntimeError("ADB trả về kích thước screenshot không hợp lệ.")
    return width, height


def compute_viewport(
    client: tuple[int, int, int, int],
    android_width: int,
    android_height: int,
    override: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int]:
    left, top, client_width, client_height = client
    if override:
        x, y, width, height = override
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("--viewport cần x,y,width,height hợp lệ, tính từ góc trên-trái client area.")
        if x + width > client_width or y + height > client_height:
            raise ValueError("--viewport vượt ra ngoài client area của cửa sổ.")
        return left + x, top + y, width, height

    # Fit Android's aspect ratio into the client rectangle, assuming centered rendering.
    android_ratio = android_width / android_height
    client_ratio = client_width / client_height
    if client_ratio > android_ratio:
        width = round(client_height * android_ratio)
        height = client_height
        x = left + (client_width - width) // 2
        y = top
    else:
        width = client_width
        height = round(client_width / android_ratio)
        x = left
        y = top + (client_height - height) // 2
    return x, y, width, height


def main() -> int:
    parser = argparse.ArgumentParser(
        description="F8 ghi tọa độ chuột; F9 chọn 4 góc vùng phân tích trực tiếp trên LDPlayer."
    )
    parser.add_argument("--serial", default="emulator-5554", help="ADB serial, ví dụ emulator-5554")
    parser.add_argument("--window-title", default="LDPlayer", help="Chuỗi trong tiêu đề cửa sổ LDPlayer")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="File JSON lưu vùng 4 góc")
    parser.add_argument("--name", default="analysis_region", help="Tên vùng cần lưu trong JSON")
    parser.add_argument(
        "--viewport",
        help="Tùy chọn x,y,width,height của vùng Android tính từ góc trên-trái client area, nếu tự động căn không khớp",
    )
    args = parser.parse_args()

    try:
        hwnd, title, client = find_ldplayer_window(args.window_title)
        android_width, android_height = load_device_resolution(args.serial)
    except Exception as exc:
        print(f"Lỗi khởi động: {exc}")
        return 1

    viewport_override = None
    if args.viewport:
        try:
            parts = tuple(int(part.strip()) for part in args.viewport.split(","))
            if len(parts) != 4:
                raise ValueError
            viewport_override = parts
        except ValueError:
            print("--viewport phải có dạng x,y,width,height, ví dụ 0,0,960,540")
            return 1

    viewport = compute_viewport(client, android_width, android_height, viewport_override)
    output_path = Path(args.output)
    log_path = LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        encoding="utf-8",
    )

    state: dict[str, Any] = {"selecting": False, "points": [], "stopped": False}
    lock = threading.Lock()

    def convert_point(screen_x: int, screen_y: int) -> dict[str, Any] | None:
        vx, vy, vw, vh = viewport
        if not (vx <= screen_x < vx + vw and vy <= screen_y < vy + vh):
            return None
        android_x = round((screen_x - vx) * android_width / vw)
        android_y = round((screen_y - vy) * android_height / vh)
        android_x = min(android_width - 1, max(0, android_x))
        android_y = min(android_height - 1, max(0, android_y))
        return {
            "windows_x": screen_x,
            "windows_y": screen_y,
            "android_x": android_x,
            "android_y": android_y,
            "x_ratio": round(android_x / android_width, 6),
            "y_ratio": round(android_y / android_height, 6),
        }

    def record_point(screen_x: int, screen_y: int) -> None:
        converted = convert_point(screen_x, screen_y)
        if converted is None:
            message = f"Con trỏ Windows=({screen_x},{screen_y}) nằm ngoài viewport Android."
            print(message)
            logging.info(message)
            return
        with lock:
            if not state["selecting"]:
                message = (
                    f"F8: Android=({converted['android_x']},{converted['android_y']}), "
                    f"Windows=({converted['windows_x']},{converted['windows_y']}), "
                    f"ratio=({converted['x_ratio']},{converted['y_ratio']})"
                )
                print(message)
                logging.info(message)
                return

            state["points"].append(converted)
            index = len(state["points"])
            names = ["trên-trái", "trên-phải", "dưới-phải", "dưới-trái"]
            line = (
                f"Vùng {args.name} - điểm {index}/4 ({names[index - 1]}): "
                f"Android=({converted['android_x']},{converted['android_y']}), "
                f"Windows=({converted['windows_x']},{converted['windows_y']})"
            )
            print(line)
            logging.info(line)
            if index != 4:
                print(f"Di chuyển chuột đến góc {names[index]} rồi nhấn F8 để ghi điểm tiếp theo.")
                return

            points = list(state["points"])
            xs = [p["android_x"] for p in points]
            ys = [p["android_y"] for p in points]
            region = {
                "name": args.name,
                "serial": args.serial,
                "window_title": title,
                "android_resolution": [android_width, android_height],
                "viewport_screen_rect": {
                    "x": viewport[0], "y": viewport[1],
                    "width": viewport[2], "height": viewport[3],
                },
                "corners_order": ["top_left", "top_right", "bottom_right", "bottom_left"],
                "corners": points,
                "bounds_android": {
                    "left": min(xs), "top": min(ys),
                    "right": max(xs), "bottom": max(ys),
                    "width": max(xs) - min(xs), "height": max(ys) - min(ys),
                },
                "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            try:
                if output_path.exists():
                    existing = json.loads(output_path.read_text(encoding="utf-8"))
                else:
                    existing = {"regions": {}}
                if not isinstance(existing, dict):
                    raise ValueError("Cấu trúc JSON gốc phải là object.")
                existing.setdefault("regions", {})
                if not isinstance(existing["regions"], dict):
                    raise ValueError("Khóa 'regions' trong JSON phải là object.")
                existing["regions"][args.name] = region
                output_path.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                message = f"Đã lưu vùng {args.name!r} vào {output_path}"
                print(message)
                logging.info(message)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(f"Không lưu được JSON: {exc}")
                logging.exception("Lưu vùng thất bại")
            state["selecting"] = False
            state["points"] = []
            print("Đã kết thúc chọn vùng. Nhấn F9 để chọn vùng khác, F8 để ghi một điểm.")
 
    def on_press(key: keyboard.Key | keyboard.KeyCode) -> None:
        if key == keyboard.Key.f8:
            point = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            record_point(point.x, point.y)
        elif key == keyboard.Key.f9:
            with lock:
                state["points"] = []
                state["selecting"] = True
            print("Di chuyển chuột đến góc trên-trái rồi nhấn F8; tiếp tục trên-phải, dưới-phải, dưới-trái.")
            print("Chế độ này không click vào game, chỉ ghi vị trí con trỏ bằng hotkey F8.")
            logging.info("Bắt đầu chọn vùng %s", args.name)
        elif key == keyboard.Key.esc:
            with lock:
                if state["selecting"]:
                    state["selecting"] = False
                    state["points"] = []
                    print("Đã hủy chọn vùng.")
                    logging.info("Đã hủy chọn vùng")
                else:
                    state["stopped"] = True
                    print("Đã thoát công cụ.")
                    logging.info("Thoát công cụ")
                    return False
        return None

    print(f"Cửa sổ: {title}")
    print(f"Client area trên Windows: {client[2]}x{client[3]} tại ({client[0]},{client[1]})")
    print(f"Độ phân giải Android từ ADB: {android_width}x{android_height}")
    print(f"Viewport được dùng: {viewport[2]}x{viewport[3]} tại ({viewport[0]},{viewport[1]})")
    print(f"Nhật ký: {log_path.resolve()}")
    print(f"JSON vùng: {output_path.resolve()}")
    print("F8 = ghi tọa độ / ghi góc kế tiếp | F9 = bắt đầu chọn 4 góc | ESC = hủy chọn hoặc thoát")
    print("Giữ LDPlayer mở và không thay đổi kích thước cửa sổ trong lúc chọn.")

    with keyboard.Listener(on_press=on_press) as keyboard_listener:
        keyboard_listener.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
