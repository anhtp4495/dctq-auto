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

    def _mock_tick(self, message: str) -> bool:
        """Log one simulated action, respecting pause and stop requests."""
        if not self._wait_if_paused():
            self.log_message.emit("[MOCK] Đã dừng theo yêu cầu.")
            return False
        time.sleep(0.12)
        if self.isInterruptionRequested():
            self.log_message.emit("[MOCK] Đã dừng theo yêu cầu.")
            return False
        self.log_message.emit(f"[MOCK] {message}")
        return True

    def _simulate_battles(self, task: str, count: int, required_flags: int,
                          time_limit: int | None) -> bool:
        for number in range(1, count + 1):
            elapsed = 0
            while True:
                if not self._wait_if_paused():
                    self.log_message.emit("[MOCK] Đã dừng theo yêu cầu.")
                    return False
                time.sleep(0.12)
                elapsed += 3
                won = time_limit is None and elapsed >= 9
                flags = min(max(elapsed // 3 - 1, 0), required_flags)
                if task == "Giao tranh":
                    snapshot = BattleSnapshot(elapsed, won, flags)
                    result = run_mock_battle(self._config, [snapshot])
                    finished = result.finished
                    reason = result.reason
                elif time_limit is not None:
                    finished = elapsed >= time_limit
                    reason = "time_limit_reached" if finished else "time_limit_not_reached"
                elif not won:
                    finished, reason = False, "battle_not_won"
                elif flags >= required_flags:
                    finished, reason = True, f"win_with_{required_flags}_flags"
                else:
                    finished, reason = False, "flags_not_reached"
                if not self._mock_tick(
                    f"{task} {number}/{count}: t={elapsed}s, "
                    f"{'thắng' if won else 'chưa thắng'}, {flags} cờ."
                ):
                    return False
                if finished:
                    if not self._mock_tick(f"Kết thúc {task} {number}: {reason}."):
                        return False
                    break
        return True

    def _run_mock(self) -> None:
        """Simulate configured tasks without connecting to ADB."""
        tasks: list[tuple[str, int]] = []
        if self._config.get("thuc_hien_giao_tranh"):
            tasks.append(("Giao tranh", int(self._config.get("giao_tranh", 1))))
        if self._config.get("thuc_hien_tranh_ba"):
            tasks.append(("Tranh bá", int(self._config.get("tranh_ba", 1))))
        for key, label in (
            ("diem_danh", "Điểm danh"),
            ("bao_danh_quan_doan", "Báo danh quân đoàn"),
            ("thiet_lap_muu_binh", "Thiết lập mưu binh"),
            ("nhiem_vu_luu_ly_thap", "Nhiệm vụ Lưu Ly Tháp"),
        ):
            if self._config.get(key):
                tasks.append((label, 1))
        for key, label in (
            ("dong_gop_knb", "Đóng góp KNB"),
            ("tham_do_lanh_dia", "Thăm dò lãnh địa"),
        ):
            if self._config.get(key):
                tasks.append((label, int(self._config.get(
                    "so_lan_dong_gop_knb" if key == "dong_gop_knb"
                    else "so_lan_tham_do_lanh_dia", 1
                ))))

        total = sum(count for _, count in tasks)
        if total == 0:
            self.log_message.emit("[MOCK] Không có nhiệm vụ nào được chọn.")
            self.progress_changed.emit(1, 1, "Không có nhiệm vụ được chọn")
            return

        self.log_message.emit(
            f"[MOCK] Bắt đầu mô phỏng {len(tasks)} nhóm nhiệm vụ, "
            f"{total} lượt. Không kết nối ADB và không điều khiển game."
        )
        completed = 0
        for task, count in tasks:
            if not self._wait_if_paused():
                self.log_message.emit("[MOCK] Đã dừng theo yêu cầu.")
                return
            if task in ("Giao tranh", "Tranh bá"):
                is_giao_tranh = task == "Giao tranh"
                if is_giao_tranh:
                    if self._config.get("ha_chien_cong"):
                        if not self._mock_tick(
                            f"Hạ chiến công: mô phỏng mục tiêu "
                            f"{self._config.get('chien_cong', 200)}."
                        ):
                            return
                    elif self._config.get("chon_nha_npc"):
                        if not self._mock_tick("Chọn nhà NPC: mô phỏng chọn mục tiêu."):
                            return
                    if self._config.get("su_dung_canh_bat_tran"):
                        if not self._mock_tick("Canh Bát Trân: mô phỏng kích hoạt."):
                            return
                    flags = 3
                    limit = self._config.get("thoi_gian_giao_tranh")
                    if self._config.get("giao_tranh_nhanh_1_co"):
                        flags = 1
                else:
                    if self._config.get("mua_luot_knb"):
                        if not self._mock_tick("Tranh bá: mô phỏng mua lượt bằng KNB."):
                            return
                    flags = int(self._config.get("tranh_ba_fast_mode", 4))
                    limit = self._config.get("thoi_gian_tranh_ba")
                if not self._simulate_battles(task, count, flags, limit):
                    return
                completed += count
            else:
                for number in range(1, count + 1):
                    extras = []
                    if task == "Đóng góp KNB":
                        extras.append(f"lượt {number}/{count}")
                    if task == "Thăm dò lãnh địa":
                        extras.append(
                            "có mua lượt bằng KNB" if self._config.get("tham_do_lanh_dia_knb")
                            else "chỉ dùng lượt miễn phí"
                        )
                    suffix = f" ({', '.join(extras)})" if extras else ""
                    if not self._mock_tick(f"{task}: mô phỏng hoàn tất{suffix}."):
                        return
                    completed += 1
                    self.progress_changed.emit(
                        completed, total, f"Mock: hoàn thành {completed}/{total} lượt"
                    )
            self.progress_changed.emit(
                completed, total, f"Mock: hoàn thành {completed}/{total} lượt"
            )
        self.log_message.emit("[MOCK] Hoàn tất mô phỏng tất cả nhiệm vụ.")

    def run(self) -> None:
        if self._mock_mode:
            self.progress_changed.emit(0, 1, "Đang chuẩn bị mô phỏng")
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
