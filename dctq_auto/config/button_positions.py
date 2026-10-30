"""Load, truy xuất và lưu tọa độ các nút giao diện.

Quy ước tọa độ ADB: x là trục ngang (trái → phải), y là trục dọc
(trên → dưới). Với màn hình 1080x1920, x thuộc chiều rộng 1080 và
y thuộc chiều cao 1920. File JSON không hỗ trợ comment; ghi chú quy ước
ở đây để tránh nhầm lẫn khi nhập tọa độ.
"""

import json
from pathlib import Path
from typing import Dict, Tuple


DEFAULT_BUTTON_POSITIONS = Path(__file__).with_name("button_positions.json")


class ButtonPositions:
    """Quản lý tọa độ nút theo nhóm màn hình."""

    def __init__(self, json_path: str | Path | None = None) -> None:
        self.json_path = Path(json_path) if json_path is not None else DEFAULT_BUTTON_POSITIONS
        self.positions: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.load()

    def load(self) -> None:
        """Đọc tọa độ từ JSON; nếu file chưa tồn tại thì khởi tạo dữ liệu rỗng."""
        if not self.json_path.exists():
            self.positions = {}
            return

        with self.json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(f"Dữ liệu tọa độ nút phải là JSON object: {self.json_path}")

        self.positions = data

    def get(self, screen: str, button: str) -> Tuple[int, int]:
        """Trả về (x, y); phát sinh KeyError nếu chưa cấu hình."""
        position = self.positions[screen][button]
        x, y = position["x"], position["y"]
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(f"Tọa độ {screen}.{button} phải là số nguyên.")
        if x < 0 or y < 0:
            raise ValueError(f"Tọa độ {screen}.{button} chưa được cấu hình hợp lệ: ({x}, {y}).")
        return x, y

    def set(self, screen: str, button: str, *, x: int, y: int) -> None:
        """Cập nhật tọa độ trong bộ nhớ; gọi save() để ghi xuống JSON."""
        if not isinstance(x, int) or not isinstance(y, int):
            raise TypeError("Tọa độ x và y phải là số nguyên.")
        self.positions.setdefault(screen, {})[button] = {"x": x, "y": y}

    def save(self) -> None:
        """Ghi toàn bộ tọa độ xuống JSON."""
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with self.json_path.open("w", encoding="utf-8") as file:
            json.dump(self.positions, file, ensure_ascii=False, indent=2)
            file.write("\n")
