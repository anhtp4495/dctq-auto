"""Background workers for GUI actions."""

import time
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Signal

from dctq_auto.adb.client import AdbClient
from dctq_auto.automation.battle_testkit import BattleSnapshot, run_mock_battle


class BotWorker(QThread):
    """Run mock battle logic or the current ADB preparation flow."""

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)

    def __init__(
        self,
        serial: str | None,
        screenshot_dir: Path,
        config: dict,
        mock_mode: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._serial = serial
        self._screenshot_dir = screenshot_dir
        self._config = config
        self._mock_mode = mock_mode
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

    def _run_mock(self) -> None:
        """Simulate Giao tranh decisions without connecting to ADB."""
        if not self._config.get("thuc_hien_giao_tranh", False):
            self.progress_changed.emit(1, 1, "Không chọn Giao tranh")
            self.log_message.emit(
                "Mock hiện chỉ mô phỏng Giao tranh; mục này đang được tắt."
            )
            return

        total_battles = int(self._config.get("giao_tranh", 1))
        self.log_message.emit(
            f"[MOCK] Bắt đầu mô phỏng {total_battles} trận Giao tranh. "
            "Không kết nối ADB và không điều khiển game."
        )
        completed = 0

        for battle_number in range(1, total_battles + 1):
            if not self._wait_if_paused():
                self.log_message.emit("[MOCK] Đã dừng theo yêu cầu.")
                return

            timeline = []
            elapsed = 0
            while True:
                if not self._wait_if_paused():
                    self.log_message.emit("[MOCK] Đã dừng theo yêu cầu.")
                    return

                # One mock tick represents three simulated seconds.
                time.sleep(0.1)
                elapsed += 3
                # Time-limit scenarios deliberately never win so the
                # log demonstrates that the timer ends the battle regardless.
                won = (
                    self._config.get("thoi_gian_giao_tranh") is None
                    and elapsed >= 9
                )
                snapshot = BattleSnapshot(
                    elapsed_seconds=elapsed,
                    won=won,
                    flags=min(max(elapsed // 3 - 1, 0), 3),
                )
                timeline.append(snapshot)
                self.log_message.emit(
                    f"[MOCK] Trận {battle_number}/{total_battles}: "
                    f"t={snapshot.elapsed_seconds}s, "
                    f"{'thắng' if snapshot.won else 'chưa thắng'}, "
                    f"{snapshot.flags} cờ."
                )
                result = run_mock_battle(self._config, timeline)
                # run_mock_battle replays the whole timeline; only finish this
                # simulated battle once its configured stop condition is met.
                if result.finished:
                    self.log_message.emit(
                        f"[MOCK] Kết thúc trận {battle_number}: {result.reason}."
                    )
                    break

            completed += 1
            self.progress_changed.emit(
                completed,
                total_battles,
                f"Mock Giao tranh: hoàn thành {completed}/{total_battles} trận",
            )

        self.log_message.emit("[MOCK] Hoàn tất mô phỏng Giao tranh.")

    def run(self) -> None:
        if self._mock_mode:
            self.progress_changed.emit(0, max(1, int(self._config.get("giao_tranh", 1))), "Đang mô phỏng Giao tranh")
            self.log_message.emit(f"Bắt đầu với cấu hình: {self._config}")
            try:
                self._run_mock()
            except Exception as exc:
                self.log_message.emit(f"[MOCK] Lỗi mô phỏng: {exc}")
            return

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
                "Chưa thực hiện nhiệm vụ trong game: logic gameplay thật chưa được triển khai."
            )
        except Exception as exc:
            self.log_message.emit(f"Lỗi: {exc}")
