"""Background workers for GUI actions."""

import re
import shlex
import time
import unicodedata
from types import SimpleNamespace
from pathlib import Path
from threading import Event

import cv2
import numpy as np
import pytesseract
from PIL import ImageOps
from PySide6.QtCore import QThread, Signal

from dctq_auto.adb.client import AdbClient
from dctq_auto.automation.battle_testkit import BattleSnapshot, run_mock_battle
from dctq_auto.tasks.registry import get_enabled_tasks
from dctq_auto.tasks.common.accounts import load_accounts
from dctq_auto.tasks.common.ocr_worker import OcrWorkerMixin
from dctq_auto.tasks.activity.worker import ActivityWorkerMixin
from dctq_auto.tasks.guild.worker import GuildWorkerMixin
from dctq_auto.tasks.strategy.worker import StrategyWorkerMixin


class BotWorker(OcrWorkerMixin, ActivityWorkerMixin, GuildWorkerMixin, StrategyWorkerMixin, QThread):
    """Run test battle logic or the current ADB preparation flow."""

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)
    task_progress_changed = Signal(str, str, int, int)
    clone_account_result = Signal(str, bool)

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
        self._progress_total = 1
        self._progress_completed = 0

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
            self.log_message.emit("Đã dừng theo yêu cầu.")
            return False
        time.sleep(0.12)
        if self.isInterruptionRequested():
            self.log_message.emit("Đã dừng theo yêu cầu.")
            return False
        self.log_message.emit(f"{message}")
        return True

    @staticmethod
    def _estimated_task_seconds(task: str, config: dict) -> int:
        """Ước tính thời lượng để phân bổ tiến trình tổng theo thời gian."""
        if task == "Giao tranh":
            return max(1, int(config.get("thoi_gian_giao_tranh") or 180))
        if task == "Tranh bá":
            return max(1, int(config.get("thoi_gian_tranh_ba") or 180))
        return 30

    def _emit_mock_progress(self, partial_units: int, status: str) -> None:
        value = min(self._progress_total, self._progress_completed + max(0, partial_units))
        self.progress_changed.emit(value, self._progress_total, status)

    def _simulate_battles(self, task: str, count: int, required_flags: int,
                          time_limit: int | None) -> bool:
        for number in range(1, count + 1):
            elapsed = 0
            while True:
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return False
                time.sleep(0.12)
                elapsed += 3
                won = time_limit is None and elapsed >= 9
                flags = min(max(elapsed // 3 - 1, 0), required_flags)
                if task == "Giao tranh":
                    snapshot = BattleSnapshot(elapsed, won, flags)
                    result = run_mock_battle(self._config, [snapshot])
                    finished, reason = result.finished, result.reason
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
                # Overall progress advances only when a battle is completed.
                self._emit_mock_progress(0, f"{task}: trận {number}/{count}")
                if finished:
                    if not self._mock_tick(f"Kết thúc {task} {number}: {reason}."):
                        return False
                    self.task_progress_changed.emit(task, "running", number, count)
                    self._progress_completed += 1
                    self._emit_mock_progress(0, f"Hoàn thành lượt {self._progress_completed}/{self._progress_total}: {task} {number}/{count}")
                    break
        return True

    def _run_mock(self) -> None:
        """Simulate configured tasks and update progress without connecting to ADB."""
        if self._config.get("strategy_mode"):
            selected = ["Vào màn hình Mưu Binh"]
            if self._config.get("thiet_lap_muu_binh"):
                selected.append("Thiết lập phòng thủ")
            if self._config.get("vuot_ai_muu_binh"):
                selected.append("Vượt Ải")
            selected.append("Thoát màn hình Mưu Binh")
            self.progress_changed.emit(0, len(selected), "Bắt đầu Mưu Binh")
            for index, task in enumerate(selected, start=1):
                self.task_progress_changed.emit(task, "running", 0, 1)
                if not self._mock_tick(f"[Chạy thử] Thực hiện: {task}"):
                    self.task_progress_changed.emit(task, "stopped", 0, 1)
                    return
                self.task_progress_changed.emit(task, "done", 1, 1)
                self.progress_changed.emit(index, len(selected), task)
            return
        if self._config.get("utility_tasks_mode"):
            selected = []
            if self._config.get("task_login"):
                selected.append("Đăng nhập")
            if self._config.get("task_open_activity"):
                selected.append("Mở màn hình Hoạt động")
            if self._config.get("task_select_phuc_loi"):
                selected.append("Chọn Phúc Lợi")
            if self._config.get("nhan_le_bao_quoc_van"):
                selected.append("Nhận lễ bao quốc vận")
            if self._config.get("diem_danh"):
                selected.append("Điểm danh")
            if self._config.get("task_close_activity"):
                selected.append("Tắt màn hình Hoạt động")
            if self._config.get("bao_danh_quan_doan"):
                selected.append("Báo danh quân đoàn")
            if self._config.get("dong_gop_knb"):
                selected.append("Đóng góp KNB")
            if self._config.get("tham_do_lanh_dia"):
                selected.append("Thăm dò lãnh địa")
            if self._config.get("nhiem_vu_luu_ly_thap"):
                selected.append("Lưu Ly Tháp")
            if self._config.get("thuc_hien_giao_tranh"):
                selected.append("Giao tranh")
            if self._config.get("thuc_hien_tranh_ba"):
                selected.append("Tranh bá")
            if self._config.get("task_enter_strategy"):
                selected.append("Vào màn hình Mưu Binh")
            if self._config.get("task_strategy_defense"):
                selected.append("Thiết lập phòng thủ")
            if self._config.get("task_detect_strategy_status"):
                selected.append("Phát hiện trạng thái Mưu Binh")
            if self._config.get("task_strategy_vuot_ai"):
                selected.append("Vượt Ải")
            if self._config.get("task_receive_strategy_reward"):
                selected.append("Nhận thưởng Mưu Binh")
            if self._config.get("task_close_strategy"):
                selected.append("Thoát màn hình Mưu Binh")
            if self._config.get("task_close_guild"):
                selected.append("Thoát màn hình Quân đoàn")
            if self._config.get("task_switch_account"):
                selected.append("Đổi tài khoản")
            if self._config.get("task_click_coordinates"):
                selected.append("Click theo tọa độ")
            self.progress_changed.emit(0, max(1, len(selected)), "Bắt đầu tác vụ")
            for index, task in enumerate(selected, start=1):
                self.task_progress_changed.emit(task, "running", 0, 1)
                if not self._mock_tick(f"[Chạy thử] Thực hiện: {task}"):
                    self.task_progress_changed.emit(task, "stopped", 0, 1)
                    return
                self.task_progress_changed.emit(task, "done", 1, 1)
                self.progress_changed.emit(index, max(1, len(selected)), task)
            if not selected:
                self.log_message.emit("Tab Tác vụ: chưa chọn tác vụ nào.")
            return
        if self._config.get("clone_mode"):
            self._run_clone_mock()
            return
        tasks = [(spec.label, count) for spec, count in get_enabled_tasks(self._config)]

        # Count every configured run, not estimated seconds or task groups.
        total = sum(count for _task, count in tasks)
        if total == 0:
            self.log_message.emit("Không có nhiệm vụ nào được chọn.")
            self.progress_changed.emit(0, 0, "Không có nhiệm vụ được chọn")
            return

        self._progress_total = total
        self._progress_completed = 0
        self.progress_changed.emit(0, self._progress_total, "Bắt đầu")
        self.log_message.emit(
            f"Bắt đầu chạy thử {len(tasks)} nhóm nhiệm vụ, tổng cộng {total} lượt. "
            f"Không kết nối ADB và không điều khiển game."
        )
        for task, count in tasks:
            self.task_progress_changed.emit(task, "running", 0, count)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if task in ("Giao tranh", "Tranh bá"):
                is_giao_tranh = task == "Giao tranh"
                if is_giao_tranh:
                    if self._config.get("ha_chien_cong"):
                        if not self._mock_tick(
                            f"Hạ chiến công: chạy thử mục tiêu {self._config.get('chien_cong', 200)}."
                        ):
                            return
                    elif self._config.get("chon_nha_npc"):
                        if not self._mock_tick("Chọn nhà NPC: chạy thử chọn mục tiêu."):
                            return
                    if self._config.get("su_dung_canh_bat_tran"):
                        if not self._mock_tick("Canh Bát Trân: chạy thử kích hoạt."):
                            return
                    flags = 1 if self._config.get("giao_tranh_nhanh_1_co") else 3
                    limit = self._config.get("thoi_gian_giao_tranh")
                else:
                    if self._config.get("mua_luot_knb"):
                        if not self._mock_tick("Tranh bá: chạy thử mua lượt bằng KNB."):
                            return
                    flags = int(self._config.get("tranh_ba_fast_mode", 4))
                    limit = self._config.get("thoi_gian_tranh_ba")
                if not self._simulate_battles(task, count, flags, limit):
                    return
            else:
                for number in range(1, count + 1):
                    if task == "Nhiệm vụ Lưu Ly Tháp" and self._config.get("luu_ly_thap_knb"):
                        if not self._mock_tick(
                            f"{task}: chạy thử mua lượt bằng KNB ({number}/{count})."
                        ):
                            return
                    extras = []
                    if task == "Đóng góp KNB":
                        extras.append(f"lượt {number}/{count}")
                    if task == "Thăm dò lãnh địa":
                        extras.append(
                            "có mua lượt bằng KNB" if self._config.get("tham_do_lanh_dia_knb")
                            else "chỉ dùng lượt miễn phí"
                        )
                    suffix = f" ({', '.join(extras)})" if extras else ""
                    if not self._mock_tick(f"{task}: chạy thử hoàn tất{suffix}."):
                        return
                    self.task_progress_changed.emit(task, "running", number, count)
                    self._progress_completed += 1
                    self._emit_mock_progress(0, f"Hoàn thành lượt {self._progress_completed}/{total}: {task} {number}/{count}")
            self.task_progress_changed.emit(task, "done", count, count)
        self.log_message.emit("Hoàn tất chạy thử tất cả nhiệm vụ.")

    def _run_clone_mock(self) -> None:
        """Chạy thử thứ tự tài khoản/nhiệm vụ, tuyệt đối không kết nối game."""
        accounts = load_accounts(self._config.get("clone_account_file", ""))
        task_specs = (
            ("clone_login", "Đăng nhập"),
            ("clone_receive_quoc_van", "Hoạt động -> Phúc lợi -> Nhận lễ bao quốc vận"),
            ("clone_daily_check_in", "Hoạt động -> Phúc lợi -> Điểm danh"),
            ("clone_logout", "Đăng xuất"),
        )
        selected = [
            (key, label) for key, label in task_specs
            if key != "clone_logout" and self._config.get(key)
        ]
        guild_mock_tasks = (
            ("clone_guild_check_in", "Báo danh quân đoàn"),
            ("clone_receive_lucky_bag", "Nhận túi phúc"),
            ("clone_guild_fortune", "Cầu vận quân đoàn (5 lần)"),
        )
        selected_guild = [
            (key, label) for key, label in guild_mock_tasks
            if self._config.get(key)
        ]
        if selected_guild:
            selected.extend([
                ("clone_enter_guild", "Vào màn hình Quân đoàn"),
                *selected_guild,
                ("clone_close_guild", "Thoát màn hình Quân đoàn"),
            ])
        if self._config.get("clone_logout", True):
            selected.append(("clone_logout", "Đăng xuất"))
        total = len(accounts)
        if total == 0:
            self.log_message.emit("Tab Clone: không có tài khoản hoặc nhiệm vụ để chạy.")
            self.progress_changed.emit(0, 0, "Không có nhiệm vụ được chọn")
            return

        self._progress_total = total
        self._progress_completed = 0
        self.progress_changed.emit(0, total, "Bắt đầu chạy thử Clone")
        self.log_message.emit(
            f"Chạy thử Clone: {len(accounts)} tài khoản, "
            f"{len(selected)} nhiệm vụ/tài khoản. Chế độ mô phỏng, không điều khiển game."
        )
        for account_index, account in enumerate(accounts, start=1):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            self.progress_changed.emit(
                self._progress_completed, self._progress_total,
                f"Tài khoản {account_index}/{len(accounts)}: {account.username}",
            )
            self.log_message.emit(
                f"Đang xử lý tài khoản: {account.username}"
            )
            for task_index, (_key, label) in enumerate(selected, start=1):
                self.progress_changed.emit(
                    self._progress_completed, self._progress_total,
                    f"{account.username} — {label} ({task_index}/{len(selected)})",
                )
                flow_step = {
                    "clone_receive_quoc_van": 2,
                    "clone_daily_check_in": 3,
                }.get(_key, task_index)
                flow_total = 6 if _key in (
                    "clone_receive_quoc_van", "clone_daily_check_in"
                ) else len(selected)
                if not self._mock_tick(
                    f"[{account.username}] {label}: chạy thử bước "
                    f"{flow_step}/{flow_total}."
                ):
                    return
                self.task_progress_changed.emit(
                    f"{account.username} - {label}", "done", 1, 1
                )
            # Record the account only after its selected mock steps finish.
            self.clone_account_result.emit(account.username, True)
            self._progress_completed += 1
            progress_text = (
                f"Tiến trình tài khoản [{self._progress_completed}/{len(accounts)}]"
            )
            self.log_message.emit(progress_text)
            self.progress_changed.emit(
                self._progress_completed,
                self._progress_total,
                progress_text,
            )
        self.log_message.emit(
            "Hoàn tất chạy thử Clone. Đây chỉ là mô phỏng; chưa có thao tác trong game."
        )

    @staticmethod
    def _is_login_screen(text: str) -> bool:
        normalized = BotWorker._normalize_screen_text(text)
        has_password = "mat khau" in normalized
        has_username_hint = any(
            marker in normalized
            for marker in ("ten dang nhap", "so dien thoai", "email", "tai khoan")
        )
        has_login_button = "dang nhap" in normalized

        # Preferred path: OCR identifies the actual form labels/button.
        if has_login_button and (has_password or has_username_hint):
            return True

        # Fallback for the known Vietnamese login page: OCR sometimes misses
        # the input labels and button but still reads both navigation links.
        # Requiring BOTH links is more conservative than accepting either one
        # alone, and lets the caller use the saved, resolution-scaled regions.
        has_sign_up_link = "dang ky" in normalized
        has_forgot_password_link = "quen mat khau" in normalized
        return has_sign_up_link and has_forgot_password_link

    @staticmethod
    def _login_error(text: str) -> str | None:
        """Return a generic login error category without exposing credentials."""
        normalized = BotWorker._normalize_screen_text(text)
        error_phrases = (
            ("sai mat khau", "Mật khẩu không đúng"),
            ("mat khau sai", "Mật khẩu không đúng"),
            ("tai khoan khong ton tai", "Tài khoản không tồn tại"),
            ("tai khoan hoac mat khau", "Tài khoản hoặc mật khẩu không đúng"),
            ("dang nhap that bai", "Đăng nhập thất bại"),
            ("ten dang nhap khong hop le", "Tên đăng nhập không hợp lệ"),
            ("mat khau khong duoc de trong", "Chưa nhập mật khẩu"),
            ("vui long nhap mat khau", "Chưa nhập mật khẩu"),
            ("ket noi that bai", "Kết nối thất bại"),
            ("connection failed", "Kết nối thất bại"),
            ("network error", "Lỗi mạng"),
        )
        for phrase, message in error_phrases:
            if phrase in normalized:
                return message
        return None

    @staticmethod
    def _clear_focused_text(device) -> None:
        """Select and delete all text in the currently focused input field."""
        # Apply the same clearing sequence to both username and password fields.
        # Ctrl+A avoids leaving trailing characters when the old value is longer.
        device.shell("input keycombination KEYCODE_CTRL_LEFT KEYCODE_A")
        device.shell("input keyevent KEYCODE_DEL")

    @staticmethod
    def _input_text(device, value: str) -> None:
        """Send text safely through Android input; spaces use Android's %s syntax."""
        # Android's input command uses %s as the escape sequence for a space.
        value = value.replace(" ", "%s")
        device.shell(f"input text {shlex.quote(value)}")

    @staticmethod
    def _replace_focused_text(device, value: str) -> None:
        """Clear the focused field before entering a new username or password."""
        BotWorker._clear_focused_text(device)
        BotWorker._input_text(device, value)

    @staticmethod
    def _replace_password_text(device, value: str) -> None:
        """Clear password fields even when their widget ignores Ctrl+A."""
        # First try select-all. Some password widgets do not select their contents
        # with Ctrl+A, so also move to the end and send repeated Backspace events.
        BotWorker._clear_focused_text(device)
        device.shell("input keyevent KEYCODE_MOVE_END")
        device.shell("input keyevent " + " ".join(["KEYCODE_DEL"] * 64))
        BotWorker._input_text(device, value)

    def _run_clone_login(self, device) -> None:
        """Delegate the shared account/game flow to tasks.common."""
        from dctq_auto.tasks.clone.flow import run_clone_flow

        run_clone_flow(self, device)


    def _run_utility_tasks(self, device) -> None:
        """Run standalone actions on the currently logged-in game account."""
        from dctq_auto.tasks.common.logout import run_logout_flow

        from dctq_auto.adb.client import AdbClient

        ocr_client = AdbClient(serial=self._serial)
        # Count every selected task, including gameplay tasks that do not yet
        # have a real ADB implementation. Those tasks must be visible as failures
        # in the progress panel instead of silently being skipped.
        task_labels = (
            ("task_login", "Đăng nhập"),
            ("task_open_activity", "Mở màn hình Hoạt động"),
            ("task_select_phuc_loi", "Chọn Phúc Lợi"),
            ("nhan_le_bao_quoc_van", "Nhận lễ bao quốc vận"),
            ("task_close_activity", "Tắt màn hình Hoạt động"),
            ("diem_danh", "Điểm danh"),
            ("task_enter_guild", "Vào quân đoàn"),
            ("bao_danh_quan_doan", "Báo danh quân đoàn"),
            ("task_receive_lucky_bag", "Nhận túi phúc"),
            ("task_guild_fortune", "Cầu vận quân đoàn (5 lần)"),
            ("dong_gop_knb", "Đóng góp KNB"),
            ("tham_do_lanh_dia", "Thăm dò lãnh địa"),
            ("nhiem_vu_luu_ly_thap", "Lưu Ly Tháp"),
            ("thuc_hien_giao_tranh", "Giao tranh"),
            ("thuc_hien_tranh_ba", "Tranh bá"),
            ("task_enter_strategy", "Vào màn hình Mưu Binh"),
            ("task_strategy_defense", "Thiết lập phòng thủ"),
            ("task_detect_strategy_status", "Phát hiện trạng thái Mưu Binh"),
            ("task_strategy_vuot_ai", "Vượt Ải"),
            ("task_receive_strategy_reward", "Nhận thưởng Mưu Binh"),
            ("task_close_strategy", "Thoát màn hình Mưu Binh"),
            ("task_close_guild", "Thoát màn hình Quân đoàn"),
            ("task_switch_account", "Đổi tài khoản"),
            ("task_click_coordinates", "Click theo tọa độ"),
        )
        selected = [(key, label) for key, label in task_labels if self._config.get(key)]
        total = len(selected)
        completed = 0
        self.progress_changed.emit(0, max(1, total), "Bắt đầu tác vụ")

        # Gameplay automation for these actions is not implemented in the real
        # ADB flow yet. Report an explicit failed status for each selected task.
        implemented = {
            "task_login", "task_open_activity", "task_select_phuc_loi", "task_close_activity",
            "nhan_le_bao_quoc_van", "diem_danh", "task_enter_guild",
            "bao_danh_quan_doan", "task_receive_lucky_bag", "task_guild_fortune",
            "task_detect_strategy_status", "task_strategy_vuot_ai",
            "task_receive_strategy_reward",
            "task_close_guild", "task_switch_account", "task_click_coordinates",
        }
        for key, label in selected:
            if key in implemented:
                continue
            self.log_message.emit(
                f"{label}: LỖI — tác vụ gameplay chưa được triển khai cho ADB thật."
            )
            self.task_progress_changed.emit(label, "failed", 0, 1)
            completed += 1
            self.progress_changed.emit(
                completed, max(1, total), f"Lỗi: {label} chưa triển khai"
            )

        if self._config.get("task_login"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            username = self._config.get("login_username", "")
            password = self._config.get("login_password", "")
            if not username or not password:
                self.log_message.emit("Đăng nhập bị bỏ qua: thiếu username hoặc password.")
                self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                return
            account = SimpleNamespace(username=username, password=password)
            try:
                screen_text = self._screen_text(device)
                if not self._is_login_screen(screen_text):
                    self.log_message.emit(
                        "Không nhập thông tin vì OCR chưa xác nhận màn hình đăng nhập. "
                        "Hãy mở màn hình đăng nhập trong game rồi thử lại."
                    )
                    self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                    return
                from dctq_auto.tasks.common.login import submit_login_form, verify_login
                self.log_message.emit(f"Đang đăng nhập tài khoản {username}.")
                if not submit_login_form(self, account, device, ocr_client):
                    return
                verified, observed_error = verify_login(self, account, device, ocr_client)
                if verified is None:
                    return
                if not verified:
                    self.log_message.emit(
                        "Đăng nhập chưa được xác minh thành công"
                        + (f": {observed_error}" if observed_error else ".")
                    )
                    self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                    return
                completed += 1
                self.task_progress_changed.emit("Đăng nhập", "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đăng nhập thành công")
                self.log_message.emit(f"Đăng nhập tài khoản {username} đã được xác minh.")
            except Exception as exc:
                self.log_message.emit(f"Không thể thực hiện đăng nhập: {exc}")
                self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                return
            finally:
                # Do not retain the password in the worker configuration after use.
                self._config.pop("login_password", None)

        if self._config.get("task_open_activity"):
            label = "Mở màn hình Hoạt động"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_open_activity(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã mở màn hình Hoạt động")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Mở màn hình Hoạt động")

        if self._config.get("task_select_phuc_loi"):
            label = "Chọn Phúc Lợi"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_select_phuc_loi(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã chọn Phúc Lợi")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Chọn Phúc Lợi")

        if self._config.get("nhan_le_bao_quoc_van"):
            label = "Nhận lễ bao quốc vận"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if self._run_receive_quoc_van(device, ocr_client):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã nhận lễ bao Quốc vận"
                )
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Lỗi: Nhận lễ bao Quốc vận"
                )

        if self._config.get("diem_danh"):
            self.task_progress_changed.emit("Điểm danh", "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if self._run_daily_checkin(device, ocr_client):
                completed += 1
                self.task_progress_changed.emit("Điểm danh", "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã mở mục Điểm danh"
                )
            else:
                self.task_progress_changed.emit("Điểm danh", "failed", 0, 1)
                completed += 1
                self.progress_changed.emit(
                    completed, max(1, total), "Lỗi: Điểm danh"
                )

        if self._config.get("task_close_activity"):
            label = "Tắt màn hình Hoạt động"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_close_activity(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã tắt màn hình Hoạt động")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Tắt màn hình Hoạt động")

        if self._config.get("task_enter_guild"):
            label = "Vào quân đoàn"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi vào Quân đoàn.")
                return
            if self._run_enter_guild(device, ocr_client):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã xác nhận vào Quân đoàn"
                )
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Lỗi: Vào quân đoàn"
                )

        for guild_task_key in (
            "bao_danh_quan_doan",
            "task_receive_lucky_bag",
            "task_guild_fortune",
        ):
            if not self._config.get(guild_task_key):
                continue
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi chạy tác vụ Quân đoàn.")
                return
            task_ok = self._run_guild_screen_task(guild_task_key, device, ocr_client)
            completed += 1
            status_label = {
                "bao_danh_quan_doan": "Báo danh quân đoàn",
                "task_receive_lucky_bag": "Nhận túi phúc",
                "task_guild_fortune": "Cầu vận quân đoàn (5 lần)",
            }[guild_task_key]
            if task_ok:
                self.progress_changed.emit(
                    completed, max(1, total), f"Hoàn tất: {status_label}"
                )
            else:
                # A requested stop is cooperative; don't continue with later actions.
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {status_label}"
                )

        if self._config.get("task_detect_strategy_status"):
            label = "Phát hiện trạng thái Mưu Binh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                _regions_path, elements = self._strategy_regions()
                status, stage = self._detect_strategy_status(device, elements)
                if status == "khong_xac_dinh":
                    raise RuntimeError("OCR chưa xác định được trạng thái Mưu Binh.")
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Trạng thái Mưu Binh: {status}"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )

        if self._config.get("task_strategy_vuot_ai"):
            label = "Vượt Ải"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_strategy_vuot_ai(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Hoàn tất Vượt Ải")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Vượt Ải")

        if self._config.get("task_receive_strategy_reward"):
            label = "Nhận thưởng Mưu Binh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                _regions_path, elements = self._strategy_regions()
                reward_ok = self._run_strategy_reward(device, elements)
            except Exception as exc:
                self.log_message.emit(f"{label} thất bại: {exc}")
                reward_ok = False
            completed += 1
            if reward_ok:
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã nhận thưởng Mưu Binh")
            else:
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), f"Lỗi: {label}")

        if self._config.get("task_close_guild"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi thoát màn hình Quân đoàn.")
                return
            try:
                import json

                regions_path = Path(__file__).resolve().parents[1] / "tasks" / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Không đọc được {regions_path}: {exc}") from exc

                self.log_message.emit(
                    "Thoát Quân đoàn — BƯỚC 1: Đóng màn hình Quân đoàn bằng close_quan_doan "
                    "lấy từ regions.json."
                )
                ocr_client.tap_ocr_target("close_quan_doan", regions_path=regions_path)
                self.log_message.emit(
                    "Đã đóng màn hình Quân đoàn; chờ 5 giây trước khi OCR nút "
                    "'vao_quan_doan' trong RECT (1270, 968, 1532, 1026)."
                )
                time.sleep(5)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi kiểm tra nút vào Quân đoàn.")
                    return

                # Chỉ OCR vùng nút "Vào quân đoàn", tránh chữ trong khung chat
                # làm nhiễu kết quả. RECT có dạng (left, top, right, bottom).
                rect = (1270, 968, 1532, 1026)
                screenshot = device.screenshot().convert("RGB")
                if screenshot.width < rect[2] or screenshot.height < rect[3]:
                    raise RuntimeError(
                        f"Screenshot {screenshot.width}x{screenshot.height} nhỏ hơn RECT {rect}"
                    )
                roi = ImageOps.autocontrast(
                    screenshot.crop(rect).convert("L")
                )
                recognized_texts = []
                for language in ("vie+eng", "eng"):
                    language_failed = False
                    for page_mode in (6, 11):
                        try:
                            text = pytesseract.image_to_string(
                                roi, lang=language, config=f"--psm {page_mode}"
                            ).strip()
                        except pytesseract.TesseractError:
                            language_failed = True
                            break
                        if text and text not in recognized_texts:
                            recognized_texts.append(text)
                    if not language_failed and recognized_texts:
                        break
                screen_text = " ".join(recognized_texts)
                normalized = self._normalize_screen_text(screen_text)
                has_enter_guild_label = "vao quan doan" in normalized
                if has_enter_guild_label:
                    self.log_message.emit(
                        "Thoát Quân đoàn — OCR tìm thấy 'vao_quan_doan'; "
                        "click tọa độ thoat_chat_quan_doan đã lưu trong regions.json."
                    )
                    x, y = ocr_client.tap_ocr_target(
                        "thoat_chat_quan_doan", regions_path=regions_path
                    )
                    self.log_message.emit(
                        f"Đã click thoat_chat_quan_doan tại ({x}, {y})."
                    )
                    time.sleep(0.8)
                else:
                    self.log_message.emit(
                        "OCR không tìm thấy 'vao_quan_doan'; bỏ qua click "
                        "thoat_chat_quan_doan vì không cần đóng chat theo điều kiện đã đặt. "
                        f"OCR: {screen_text[:220] or '(trống)'}"
                    )

                completed += 1
                self.progress_changed.emit(
                    completed, max(1, total), "Đã xử lý trạng thái chat Quân đoàn"
                )
                self.task_progress_changed.emit(
                    "Thoát màn hình Quân đoàn", "done", 1, 1
                )
                self.log_message.emit(
                    "Hoàn tất flow thoát Quân đoàn: kiểm tra 'vao_quan_doan'; "
                    "nếu có thì click thoat_chat_quan_doan theo regions.json."
                )
            except Exception as exc:
                self.log_message.emit(
                    f"Không đóng được giao diện Quân đoàn/chat: {exc}"
                )
                self.task_progress_changed.emit(
                    "Thoát màn hình Quân đoàn", "failed", 0, 1
                )

        if self._config.get("task_switch_account"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            self.log_message.emit(
                "Tác vụ: bắt đầu quy trình Đổi tài khoản; "
                "chỉ xác nhận khi OCR nhận diện đúng hộp thoại."
            )
            account = SimpleNamespace(username="Tác vụ")
            result = run_logout_flow(self, account, device, ocr_client)
            if result:
                completed += 1
                self.task_progress_changed.emit("Đổi tài khoản", "done", 1, 1)
                self.log_message.emit(
                    "Tác vụ Đổi tài khoản đã hoàn tất và đã xác minh màn hình đăng nhập."
                )
            elif result is None:
                self.log_message.emit("Tác vụ Đổi tài khoản đã dừng theo yêu cầu.")
                return
            else:
                self.log_message.emit(
                    "Tác vụ Đổi tài khoản chưa xác minh hoàn tất; kiểm tra nhật ký OCR."
                )
                self.task_progress_changed.emit("Đổi tài khoản", "failed", 0, 1)
            self.progress_changed.emit(
                completed, max(1, total), "Đổi tài khoản đã xử lý"
            )

        if self._config.get("task_click_coordinates"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            x = int(self._config.get("task_click_x", 0))
            y = int(self._config.get("task_click_y", 0))
            try:
                device.shell(f"input tap {x} {y}")
                completed += 1
                self.task_progress_changed.emit("Click theo tọa độ", "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Đã click tọa độ ({x}, {y})"
                )
                self.log_message.emit(f"Đã click theo tọa độ X={x}, Y={y}.")
            except Exception as exc:
                self.task_progress_changed.emit("Click theo tọa độ", "failed", 0, 1)
                self.progress_changed.emit(
                    completed + 1, max(1, total), "Lỗi: Click theo tọa độ"
                )
                self.log_message.emit(f"Không thể click tọa độ ({x}, {y}): {exc}")

    def run(self) -> None:
        if self._mock_mode:
            self.progress_changed.emit(0, 1, "Đang chuẩn bị chạy thử")
            self.log_message.emit("Bắt đầu với cấu hình đã chọn.")
            try:
                self._run_mock()
            except Exception as exc:
                self.log_message.emit(f"Lỗi chạy thử: {exc}")
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
            if self._config.get("strategy_mode"):
                self.log_message.emit(
                    "Tab Mưu Binh: giao diện và thứ tự tác vụ đã cấu hình; "
                    "luồng ADB sẽ được triển khai ở bước sau."
                )
                return
            if self._config.get("utility_tasks_mode"):
                self._run_utility_tasks(device)
                return
            if self._config.get("clone_mode"):
                self._run_clone_login(device)
                return
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
