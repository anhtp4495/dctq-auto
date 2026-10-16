"""Background workers for GUI actions."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from dctq_auto.adb.client import AdbClient


class BotWorker(QThread):
    """Run non-GUI work without blocking the Qt event loop.

    Gameplay automation is intentionally not invoked until its rules are defined.
    The current worker verifies ADB connectivity and captures one screenshot.
    """

    log_message = Signal(str)

    def __init__(self, serial: str | None, screenshot_dir: Path, config: dict, parent=None) -> None:
        super().__init__(parent)
        self._serial = serial
        self._screenshot_dir = screenshot_dir
        self._config = config

    def run(self) -> None:
        self.log_message.emit(
            "Bắt đầu với cấu hình: "
            f"giao_tranh={self._config['giao_tranh']}, "
            f"tranh_ba={self._config['tranh_ba']}, "
            f"mua_luot_knb={self._config['mua_luot_knb']}, "
            f"diem_danh={self._config['diem_danh']}, "
            f"bao_danh_quan_doan={self._config['bao_danh_quan_doan']}, "
            f"thiet_lap_muu_binh={self._config['thiet_lap_muu_binh']}"
        )
        if self.isInterruptionRequested():
            self.log_message.emit("Đã yêu cầu dừng trước khi kết nối ADB.")
            return

        try:
            client = AdbClient(serial=self._serial)
            device = client.connect()
            self.log_message.emit(f"Đã kết nối ADB: {self._serial}")
            if self.isInterruptionRequested():
                self.log_message.emit("Đã yêu cầu dừng trước khi chụp màn hình.")
                return
            screenshot = client.save_screenshot(device, self._screenshot_dir)
            self.log_message.emit(f"Đã lưu screenshot: {screenshot}")
            self.log_message.emit(
                "Chưa thực hiện nhiệm vụ trong game: logic gameplay chưa được triển khai."
            )
        except Exception as exc:
            self.log_message.emit(f"Lỗi: {exc}")
