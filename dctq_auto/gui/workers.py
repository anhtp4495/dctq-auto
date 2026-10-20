"""Background workers for GUI actions."""

import re
import shlex
import time
import unicodedata
from pathlib import Path
from threading import Event

import pytesseract
from PIL import ImageOps
from PySide6.QtCore import QThread, Signal

from dctq_auto.adb.client import AdbClient
from dctq_auto.automation.battle_testkit import BattleSnapshot, run_mock_battle
from dctq_auto.tasks.registry import get_enabled_tasks
from dctq_auto.tasks.common.accounts import load_accounts


class BotWorker(QThread):
    """Run test battle logic or the current ADB preparation flow."""

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)
    task_progress_changed = Signal(str, str, int, int)

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
                expected_seconds = self._estimated_task_seconds(task, self._config)
                partial = min(expected_seconds - 1, elapsed)
                self._emit_mock_progress(
                    partial, f"{task}: trận {number}/{count}"
                )
                if finished:
                    if not self._mock_tick(f"Kết thúc {task} {number}: {reason}."):
                        return False
                    self._progress_completed += expected_seconds
                    self.task_progress_changed.emit(task, "running", number, count)
                    self._emit_mock_progress(0, f"{task}: hoàn thành {number}/{count}")
                    break
        return True

    def _run_mock(self) -> None:
        """Simulate configured tasks and update progress without connecting to ADB."""
        if self._config.get("clone_mode"):
            self._run_clone_mock()
            return
        tasks = [(spec.label, count) for spec, count in get_enabled_tasks(self._config)]

        total = sum(count * self._estimated_task_seconds(task, self._config) for task, count in tasks)
        if total == 0:
            self.log_message.emit("Không có nhiệm vụ nào được chọn.")
            self.progress_changed.emit(0, 0, "Không có nhiệm vụ được chọn")
            return

        self._progress_total = total
        self._progress_completed = 0
        self.progress_changed.emit(0, self._progress_total, "Bắt đầu")
        self.log_message.emit(
            f"Bắt đầu chạy thử {len(tasks)} nhóm nhiệm vụ, "
            f"thời lượng ước tính {total} giây. Không kết nối ADB và không điều khiển game."
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
                    self._progress_completed += self._estimated_task_seconds(task, self._config)
                    self.task_progress_changed.emit(task, "running", number, count)
                    self._emit_mock_progress(
                        0, f"Đã hoàn thành {self._progress_completed // 100}/{total} lượt"
                    )
            self.task_progress_changed.emit(task, "done", count, count)
        self.log_message.emit("Hoàn tất chạy thử tất cả nhiệm vụ.")

    def _run_clone_mock(self) -> None:
        """Chạy thử thứ tự tài khoản/nhiệm vụ, tuyệt đối không kết nối game."""
        accounts = load_accounts(self._config.get("clone_account_file", ""))
        task_specs = (
            ("clone_login", "Đăng nhập"),
            ("clone_daily_check_in", "Điểm danh"),
            ("clone_guild_check_in", "Báo danh quân đoàn"),
            ("clone_receive_lucky_bag", "Nhận túi phúc"),
            ("clone_logout", "Đăng xuất"),
        )
        selected = [
            (key, label) for key, label in task_specs if self._config.get(key)
        ]
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
            self.log_message.emit(
                f"Đang xử lý tài khoản: {account.username}"
            )
            for task_index, (_key, label) in enumerate(selected, start=1):
                if not self._mock_tick(
                    f"[{account.username}] {label}: chạy thử bước "
                    f"{task_index}/{len(selected)}."
                ):
                    return
                self.task_progress_changed.emit(
                    f"{account.username} - {label}", "done", 1, 1
                )
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
    def _normalize_screen_text(text: str) -> str:
        text = unicodedata.normalize("NFD", text.lower())
        text = "".join(
            char for char in text
            if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    @staticmethod
    def _screen_text(device) -> str:
        """Read visible game text from a device screenshot using Tesseract."""
        image = device.screenshot()
        image = ImageOps.autocontrast(image.convert("L"))
        try:
            return pytesseract.image_to_string(image, lang="vie+eng", config="--psm 6")
        except pytesseract.TesseractError:
            return pytesseract.image_to_string(image, lang="eng", config="--psm 6")

    @staticmethod
    def _tap_ocr_word(device, words: tuple[str, ...]) -> bool:
        """Tap the center of a word detected in the current screenshot by OCR."""
        image = device.screenshot()
        image = ImageOps.autocontrast(image.convert("L"))
        try:
            data = pytesseract.image_to_data(
                image, lang="vie+eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                image, lang="eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )

        wanted = {BotWorker._normalize_screen_text(word) for word in words}
        candidates = []
        for i, raw in enumerate(data.get("text", [])):
            normalized = BotWorker._normalize_screen_text(raw)
            if normalized not in wanted:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            x = int(data["left"][i] + data["width"][i] / 2)
            y = int(data["top"][i] + data["height"][i] / 2)
            candidates.append((confidence, x, y, normalized))

        if not candidates:
            return False

        # Prefer the clearest recognized "dong" label. Tap the live screenshot
        # coordinates directly rather than relying on a possibly missing saved region.
        confidence, x, y, word = max(candidates)
        device.shell(f"input tap {x} {y}")
        return True

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
        from dctq_auto.tasks.common.clone_flow import run_clone_flow

        run_clone_flow(self, device)

    def run(self) -> None:
        if self._mock_mode:
            self.progress_changed.emit(0, 1, "Đang chuẩn bị chạy thử")
            self.log_message.emit(f"Bắt đầu với cấu hình: {self._config}")
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
