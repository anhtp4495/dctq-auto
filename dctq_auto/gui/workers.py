"""Background workers for GUI actions."""

from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Signal

from dctq_auto.adb.client import AdbClient


class BotWorker(QThread):
    """Run non-GUI work without blocking the Qt event loop.

    Gameplay automation is intentionally not invoked until its rules are defined.
    The current worker verifies ADB connectivity and captures one screenshot.
    """

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)

    def __init__(self, serial: str | None, screenshot_dir: Path, config: dict, parent=None) -> None:
        super().__init__(parent)
        self._serial = serial
        self._screenshot_dir = screenshot_dir
        self._config = config
        self._resume_event = Event()
        self._resume_event.set()

    def pause(self) -> None:
        self._resume_event.clear()

    def resume(self) -> None:
        self._resume_event.set()

    def _wait_if_paused(self) -> bool:
        while not self._resume_event.wait(0.1):
            if self.isInterruptionRequested():
                return False
        return not self.isInterruptionRequested()

    def run(self) -> None:
        self.progress_changed.emit(0, 2, "Đang kết nối ADB")
        self.log_message.emit(f"Bắt đầu với cấu hình: {self._config}")
        if not self._wait_if_paused():
            self.log_message.emit("Đã yêu cầu dừng trước khi kết nối ADB.")
            return

        try:
            client = AdbClient(serial=self._serial)
            device = client.connect()
            self.log_message.emit(f"Đã kết nối ADB: {self._serial}")
            self.progress_changed.emit(1, 2, "Đã kết nối ADB")

            if not self._wait_if_paused():
                self.log_message.emit("Đã yêu cầu dừng trước khi chụp màn hình.")
                return

            screenshot = client.save_screenshot(device, self._screenshot_dir)
            self.log_message.emit(f"Đã lưu screenshot: {screenshot}")
            self.progress_changed.emit(2, 2, "Hoàn tất bước chuẩn bị")
            self.log_message.emit(
                "Chưa thực hiện nhiệm vụ trong game: logic gameplay chưa được triển khai."
            )
        except Exception as exc:
            self.log_message.emit(f"Lỗi: {exc}")
