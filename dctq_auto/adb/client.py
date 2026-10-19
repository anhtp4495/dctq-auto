"""ADB device wrapper based on adbutils."""

import json
import re
import unicodedata
from pathlib import Path

from adbutils import AdbDevice, adb


class AdbClient:
    def __init__(self, serial: str | None = None) -> None:
        self.serial = serial

    @staticmethod
    def list_devices() -> list[AdbDevice]:
        """Return devices currently visible to the ADB server."""
        return adb.device_list()

    def connect(self) -> AdbDevice:
        if not self.serial:
            raise RuntimeError("Chưa chọn thiết bị ADB. Hãy quét và chọn LDPlayer.")
        device = adb.device(serial=self.serial)
        device.get_state()
        return device

    def tap_ocr_target(self, name: str, regions_path: Path | None = None) -> tuple[int, int]:
        """Tap the center of a saved OCR rectangle by its normalized name.

        Example: AdbClient(serial).tap_ocr_target("dang_nhap")
        Coordinates are scaled from the saved screenshot resolution to the live device.
        """
        if not self.serial:
            raise RuntimeError("Chưa chọn thiết bị ADB để click OCR.")
        target_name = unicodedata.normalize("NFD", name.strip().lower())
        target_name = "".join(
            char for char in target_name if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        target_name = re.sub(r"[^a-z0-9]+", "_", target_name).strip("_")
        if not target_name:
            raise ValueError("Tên OCR cần click không được để trống.")

        if regions_path is None:
            regions_path = Path("dctq_auto/tasks/clone/regions.json")
        if not regions_path.exists():
            raise FileNotFoundError(f"Chưa có file tọa độ OCR: {regions_path}")
        try:
            data = json.loads(regions_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Không đọc được tọa độ OCR {regions_path}: {exc}") from exc

        matches = []
        for region_name, region in data.get("regions", {}).items():
            if not isinstance(region, dict):
                continue
            for element in region.get("elements", []):
                if isinstance(element, dict) and element.get("name") == target_name:
                    matches.append((region_name, region, element))
        if not matches:
            raise KeyError(
                f"Không tìm thấy OCR target {target_name!r} trong {regions_path}. "
                "Hãy chạy OCR và lưu tọa độ trước."
            )
        if len(matches) > 1:
            region_names = ", ".join(match[0] for match in matches)
            raise ValueError(
                f"OCR target {target_name!r} bị trùng ở các vùng: {region_names}. "
                "Hãy dùng tên chuẩn hóa duy nhất hoặc xóa vùng trùng."
            )

        _region_name, region, element = matches[0]
        center_ratio = element.get("center_ratio")
        center = element.get("center", {})
        if not isinstance(center_ratio, dict):
            resolution = region.get("image_resolution", [])
            if len(resolution) != 2 or not resolution[0] or not resolution[1]:
                raise ValueError(f"Vùng OCR {target_name!r} thiếu độ phân giải ảnh gốc.")
            center_ratio = {
                "x": float(center.get("x_px", 0)) / float(resolution[0]),
                "y": float(center.get("y_px", 0)) / float(resolution[1]),
            }

        device = self.connect()
        resolution_text = device.shell("wm size")
        sizes = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", resolution_text)
        if sizes:
            width, height = map(int, sizes[-1])
        else:
            resolution = region.get("image_resolution", [])
            if len(resolution) != 2:
                raise RuntimeError(f"Không xác định được độ phân giải thiết bị: {resolution_text}")
            width, height = map(int, resolution)

        x = max(0, min(width - 1, round(float(center_ratio["x"]) * width)))
        y = max(0, min(height - 1, round(float(center_ratio["y"]) * height)))
        device.shell(f"input tap {x} {y}")
        return x, y

    @staticmethod
    def save_screenshot(device: AdbDevice, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "current_screen.png"
        device.screenshot().save(str(output_path))
        return output_path
