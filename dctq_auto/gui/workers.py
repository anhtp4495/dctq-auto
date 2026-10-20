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
from dctq_auto.tasks.clone.accounts import load_accounts


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
        """Log in clone accounts using the confirmed login-screen OCR coordinates."""
        accounts = load_accounts(self._config.get("clone_account_file", ""))
        total = len(accounts)
        if not self._config.get("clone_login", True):
            self.log_message.emit(
                "Clone: chưa chọn Đăng nhập; các thao tác Clone khác chưa được triển khai."
            )
            self.progress_changed.emit(0, total, f"0/{total} tài khoản thành công")
            return

        # Use saved OCR boxes so taps follow the source screenshot resolution.
        # These normalized names match the three OCR results supplied by the user.
        ocr_client = AdbClient(serial=self._serial)

        success_count = 0
        failed_count = 0
        processed_count = 0
        account_results: list[tuple[str, str]] = []

        def emit_account_progress(_status: str = "") -> None:
            self.progress_changed.emit(
                processed_count,
                total,
                f"{success_count} thành công | {failed_count} thất bại",
            )

        emit_account_progress("Bắt đầu")
        for index, account in enumerate(accounts, start=1):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return

            self.log_message.emit(
                f"[{account.username}] Kiểm tra màn hình đăng nhập ({index}/{total})."
            )
            try:
                screen_text = self._screen_text(device)
            except Exception as exc:
                failed_count += 1
                processed_count += 1
                account_results.append((account.username, f"FAILED — lỗi OCR: {exc}"))
                self.log_message.emit(
                    f"[{account.username}] FAILED — không đọc được màn hình bằng OCR: {exc}. "
                    "Bỏ qua account này và thử account tiếp theo."
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Đăng nhập", "failed", 0, 1
                )
                emit_account_progress(f"FAILED: {account.username}")
                continue

            if not self._is_login_screen(screen_text):
                normalized_screen = self._normalize_screen_text(screen_text)
                self.log_message.emit(
                    f"[{account.username}] OCR màn hình hiện tại: "
                    f"{normalized_screen[:240] or '(không đọc được chữ)'}"
                )
                failed_count += 1
                processed_count += 1
                account_results.append((account.username, "FAILED — không nhận diện được màn hình đăng nhập"))
                self.log_message.emit(
                    f"[{account.username}] FAILED — không nhận diện được màn hình đăng nhập; "
                    "bỏ qua account này. Không nhập thông tin vào màn hình chưa xác định."
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Đăng nhập", "failed", 0, 1
                )
                emit_account_progress(f"FAILED: {account.username}")
                # If an earlier account is still logged in, we cannot safely switch users
                # until logout is implemented. Otherwise try the next account.
                if success_count:
                    self.log_message.emit(
                        "Không thể tiếp tục đăng nhập account kế tiếp vì chưa có luồng đăng xuất an toàn."
                    )
                    break
                continue

            try:
                ocr_client.tap_ocr_target("ten_dang_nhap")
                time.sleep(0.25)
                self._replace_focused_text(device, account.username)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return

                ocr_client.tap_ocr_target("mat_khau")
                time.sleep(0.25)
                self._replace_password_text(device, account.password)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return

                time.sleep(0.3)
                ocr_client.tap_ocr_target("dang_nhap")
                self.log_message.emit(
                    f"[{account.username}] Đã gửi yêu cầu đăng nhập; đang xác minh kết quả."
                )
            except Exception as exc:
                failed_count += 1
                processed_count += 1
                account_results.append((account.username, f"FAILED — lỗi thao tác đăng nhập: {exc}"))
                self.log_message.emit(
                    f"[{account.username}] FAILED — không thể nhập thông tin hoặc bấm đăng nhập: "
                    f"{exc}. Bỏ qua account này và thử account tiếp theo."
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Đăng nhập", "failed", 0, 1
                )
                emit_account_progress(f"FAILED: {account.username}")
                continue

            verified = False
            previous_screen_text = None
            observed_error = None
            # Allow up to 20 seconds for the game/network to respond. Require two
            # consecutive non-login OCR readings to avoid counting a transient frame.
            for _attempt in range(20):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return
                time.sleep(1)
                try:
                    result_text = self._screen_text(device)
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Lỗi đọc màn hình khi xác minh: {exc}"
                    )
                    break

                normalized_result = self._normalize_screen_text(result_text)
                # Some game dialogs show only "khong dung"; OCR may miss the
                # rest of the message and read the confirmation button as "dong".
                if "khong dung" in normalized_result:
                    observed_error = "Thông tin đăng nhập không đúng"
                    self.log_message.emit(
                        f"[{account.username}] OCR phát hiện thông báo 'không đúng'; "
                        "đang bấm nút Đồng ý để đóng hộp thoại."
                    )
                    try:
                        # The saved dong_y region may not exist, and OCR can read
                        # only the button text "dong". Locate that word on the live
                        # screenshot first; use saved coordinates only as fallback.
                        tapped = self._tap_ocr_word(device, ("dong", "dong y", "dong y!"))
                        if not tapped:
                            ocr_client.tap_ocr_target("dong_y")
                        self.log_message.emit(
                            f"[{account.username}] Đã gửi thao tác đóng hộp thoại."
                        )
                        time.sleep(0.5)
                    except Exception as exc:
                        self.log_message.emit(
                            f"[{account.username}] Không bấm được nút Đồng ý: {exc}"
                        )
                    break

                # A first-login profile update dialog may appear instead of the
                # wrong-credentials dialog. Close it so the profile can finish loading.
                if "cap nhat thong tin ca nhan" in normalized_result:
                    self.log_message.emit(
                        f"[{account.username}] Phát hiện hộp thoại cập nhật thông tin cá nhân; đang đóng hộp thoại."
                    )
                    try:
                        ocr_client.tap_ocr_target("close_cap_nhat_thong_tin_ca_nhan")
                        time.sleep(1)
                        previous_screen_text = None
                        continue
                    except Exception as exc:
                        self.log_message.emit(
                            f"[{account.username}] Không đóng được hộp thoại cập nhật thông tin cá nhân: {exc}"
                        )
                        break

                observed_error = self._login_error(result_text) or observed_error
                if self._is_login_screen(result_text):
                    previous_screen_text = None
                    continue
                if not result_text.strip():
                    previous_screen_text = None
                    continue

                # Consider login successful only after the wrong-credentials dialog
                # is absent and OCR no longer sees the login button on consecutive frames.
                if "dang nhap" not in normalized_result and not observed_error:
                    if previous_screen_text is not None:
                        verified = True
                        break
                previous_screen_text = result_text

            if not verified:
                failed_count += 1
                processed_count += 1
                if observed_error:
                    reason = observed_error
                else:
                    reason = "không xác nhận được đăng nhập thành công sau 20 giây"
                account_results.append((account.username, f"FAILED — {reason}"))
                self.log_message.emit(
                    f"[{account.username}] FAILED — {reason}. "
                    "Bỏ qua account này và chuyển sang account tiếp theo."
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Đăng nhập", "failed", 0, 1
                )
                emit_account_progress(f"FAILED: {account.username}")
                continue

            # The game may need extra time to finish loading the profile.
            # "Quan chức" is the trusted profile marker; OCR can include its level
            # after it (for example, "Quan chức 4768").
            profile_found = False
            self.log_message.emit(
                f"[{account.username}] Đăng nhập có vẻ thành công; xác minh bằng cách mở mục profile."
            )
            # Tap the profile icon, then check for the "Thông tin của tôi" panel.
            try:
                ocr_client.tap_ocr_target("profile")
                time.sleep(1)
            except Exception as exc:
                self.log_message.emit(
                    f"[{account.username}] Không mở được mục profile bằng tọa độ OCR: {exc}"
                )

            for profile_attempt in range(30):  # up to ~60 seconds
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return
                if profile_attempt:
                    time.sleep(2)
                try:
                    profile_text = self._screen_text(device)
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Lỗi OCR khi chờ profile: {exc}"
                    )
                    continue

                normalized_profile = self._normalize_screen_text(profile_text)
                # The opened profile panel is identified by its title, then closed
                # with the saved top-right close target so the game returns to normal.
                if "thong tin cua toi" in normalized_profile:
                    try:
                        ocr_client.tap_ocr_target("close_thong_tin_cua_toi")
                        time.sleep(0.7)
                        profile_found = True
                        self.log_message.emit(
                            f"[{account.username}] Đã xác minh profile qua tiêu đề 'Thông tin của tôi' và đóng bảng profile."
                        )
                    except Exception as exc:
                        self.log_message.emit(
                            f"[{account.username}] Nhận diện được profile nhưng không đóng được bảng thông tin: {exc}"
                        )
                    break

            if not profile_found:
                failed_count += 1
                processed_count += 1
                account_results.append((account.username, "FAILED — không thấy profile quan_chuc sau 60 giây"))
                self.log_message.emit(
                    f"[{account.username}] FAILED — không thấy profile 'quan_chuc' sau 60 giây; "
                    "bỏ qua account này và thử account tiếp theo."
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Đăng nhập", "failed", 0, 1
                )
                emit_account_progress(f"FAILED: {account.username}")
                # Profile may be logged in but not recognized. Avoid entering another
                # account on an unknown screen unless a safe logout flow exists.
                if index < total:
                    self.log_message.emit(
                        "Tạm dừng chuyển account vì chưa xác nhận được màn hình đăng nhập sau lỗi profile."
                    )
                    break
                continue

            if self._config.get("clone_guild_check_in"):
                # Open the guild chat/entry panel, then only enter the guild when
                # OCR confirms one of the trusted labels supplied by the user.
                self.task_progress_changed.emit(
                    f"{account.username} - Báo danh quân đoàn", "running", 0, 1
                )
                try:
                    self.log_message.emit(
                        f"[{account.username}] Đang mở mục Quân đoàn qua nút chat quân đoàn."
                    )
                    ocr_client.tap_ocr_target("button_chat_quan_doan")
                    time.sleep(1.5)
                    guild_entry_found = False
                    last_guild_text = ""
                    for guild_attempt in range(5):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        last_guild_text = self._normalize_screen_text(self._screen_text(device))
                        trusted_guild_labels = (
                            "quoc chien", "su do", "quoc chien do",
                            "doan truong", "doan pho", "quan su",
                            "thanh vien", "tinh anh", "toi can tang vien",
                        )
                        if any(label in last_guild_text for label in trusted_guild_labels):
                            guild_entry_found = True
                            self.log_message.emit(
                                f"[{account.username}] OCR xác nhận giao diện chat/quân đoàn: "
                                f"{last_guild_text[:220]}"
                            )
                            break
                        if guild_attempt < 4:
                            time.sleep(1)
                    if not guild_entry_found:
                        # OCR can miss the trusted labels on the chat screen. The user
                        # confirmed that the game is already showing the guild chat, so
                        # cautiously try the known entry button once, then inspect again.
                        self.log_message.emit(
                            f"[{account.username}] Chưa thấy từ khóa tin cậy; thử bấm "
                            "'Vào quân đoàn' một lần và kiểm tra màn hình sau đó."
                        )
                    ocr_client.tap_ocr_target("vao_quan_doan")
                    time.sleep(2)
                    try:
                        after_entry_text = self._normalize_screen_text(self._screen_text(device))
                    except Exception as ocr_exc:
                        after_entry_text = ""
                        self.log_message.emit(
                            f"[{account.username}] Lỗi OCR sau khi bấm Vào quân đoàn: {ocr_exc}"
                        )
                    guild_screen_markers = (
                        "doan truong", "doan pho", "quan su", "thanh vien",
                        "tinh anh", "toi can tang vien", "tin he thong",
                    )
                    if any(marker in after_entry_text for marker in guild_screen_markers):
                        self.log_message.emit(
                            f"[{account.username}] Đã xác nhận giao diện quân đoàn sau khi bấm: "
                            f"{after_entry_text[:220]}"
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Đã gửi thao tác Vào quân đoàn; chưa thấy "
                            f"từ khóa xác nhận rõ. OCR: {after_entry_text[:220] or '(trống)'}"
                        )
                    self.log_message.emit(
                        f"[{account.username}] Đang thực hiện báo danh quân đoàn."
                    )
                    ocr_client.tap_ocr_target("bao_danh_nhan_thuong")
                    time.sleep(1.5)
                    try:
                        check_in_text = self._normalize_screen_text(self._screen_text(device))
                    except Exception as ocr_exc:
                        check_in_text = ""
                        self.log_message.emit(
                            f"[{account.username}] Không đọc được OCR sau khi bấm Báo danh: {ocr_exc}"
                        )
                    self.log_message.emit(
                        f"[{account.username}] Đã gửi thao tác 'Báo danh nhận thưởng'. "
                        f"OCR sau thao tác: {check_in_text[:220] or '(trống)'}"
                    )
                    # A tap alone does not prove that the server granted the reward.
                    # Keep this task running until a reliable success marker is known.

                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Không mở được mục quân đoàn: {exc}"
                    )
                    self.task_progress_changed.emit(
                        f"{account.username} - Báo danh quân đoàn", "failed", 0, 1
                    )

            if self._config.get("clone_receive_lucky_bag"):
                try:
                    self.log_message.emit(
                        f"[{account.username}] Đang kiểm tra cửa hàng quân đoàn để mở Túi phúc."
                    )
                    shop_text = ""
                    shop_markers = (
                        "cua hang quan doan", "tui phuc", "anh hung",
                        "cau van quan doan", "lanh tui phuc",
                    )
                    for shop_attempt in range(3):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        shop_text = self._normalize_screen_text(self._screen_text(device))
                        if any(marker in shop_text for marker in shop_markers):
                            break
                        if shop_attempt < 2:
                            time.sleep(1)
                    if any(marker in shop_text for marker in shop_markers):
                        self.log_message.emit(
                            f"[{account.username}] Đã nhận diện mục Túi phúc/cửa hàng quân đoàn: "
                            f"{shop_text[:220]}"
                        )
                        ocr_client.tap_ocr_target("tui_phuc")
                        time.sleep(1.5)
                        bag_text = ""
                        bag_screen_found = False
                        for bag_attempt in range(5):
                            if not self._wait_if_paused():
                                self.log_message.emit("Đã dừng theo yêu cầu.")
                                return
                            bag_text = self._normalize_screen_text(self._screen_text(device))
                            has_count = re.search(r"\b\d+\s+30\b", bag_text) is not None
                            bag_markers = (
                                "tui phuc tuong", "tui phuc truong thanh",
                                "tui phuc knb", "co so",
                            )
                            if has_count or any(marker in bag_text for marker in bag_markers):
                                bag_screen_found = True
                                break
                            if bag_attempt < 4:
                                time.sleep(1)
                        if bag_screen_found:
                            self.log_message.emit(
                                f"[{account.username}] Đã xác nhận màn hình Túi phúc: {bag_text[:220]}"
                            )
                            for target in ("tui_phuc_thuong", "tui_phuc_truong_thanh", "tui_phuc_knb"):
                                if not self._wait_if_paused():
                                    self.log_message.emit("Đã dừng theo yêu cầu.")
                                    return
                                ocr_client.tap_ocr_target(target)
                                time.sleep(1)
                            ocr_client.tap_ocr_target("close_tui_phuc")
                            time.sleep(0.8)
                            self.log_message.emit(
                                f"[{account.username}] Đã bấm lần lượt 3 mục Túi phúc và đóng cửa sổ."
                            )
                        else:
                            self.log_message.emit(
                                f"[{account.username}] Đã bấm Túi phúc nhưng OCR chưa xác nhận "
                                f"đúng màn hình; không bấm các vị trí nhận. OCR: {bag_text[:220] or '(trống)'}"
                            )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Chưa nhận diện được cửa hàng/Túi phúc; bỏ qua để tránh bấm nhầm. "
                            f"OCR: {shop_text[:220] or '(trống)'}"
                        )
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Lỗi thao tác nhận Túi phúc: {exc}"
                    )
                    self.task_progress_changed.emit(
                        f"{account.username} - Nhận Túi phúc", "failed", 0, 1
                    )

            if self._config.get("clone_guild_fortune"):
                try:
                    self.log_message.emit(
                        f"[{account.username}] Đang mở Cầu vận quân đoàn."
                    )
                    shop_text = self._normalize_screen_text(self._screen_text(device))
                    if not any(marker in shop_text for marker in (
                        "cua hang quan doan", "cau van quan doan", "tui phuc", "anh hung"
                    )):
                        self.log_message.emit(
                            f"[{account.username}] Chưa nhận diện cửa hàng quân đoàn trước khi mở Cầu vận; "
                            f"thử kiểm tra OCR: {shop_text[:180]}"
                        )
                    ocr_client.tap_ocr_target("cau_van_quan_doan")
                    time.sleep(1.5)
                    fortune_text = ""
                    fortune_screen_found = False
                    for fortune_attempt in range(5):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        fortune_text = self._normalize_screen_text(self._screen_text(device))
                        fortune_markers = ("giai hien tai", "xepthang", "cau van")
                        if any(marker in fortune_text for marker in fortune_markers):
                            fortune_screen_found = True
                            break
                        if fortune_attempt < 4:
                            time.sleep(1)
                    if fortune_screen_found:
                        self.log_message.emit(
                            f"[{account.username}] Đã xác nhận màn hình Cầu vận: {fortune_text[:220]}"
                        )
                        for draw_attempt in range(5):
                            if not self._wait_if_paused():
                                self.log_message.emit("Đã dừng theo yêu cầu.")
                                return
                            ocr_client.tap_ocr_target("cau_van")
                            time.sleep(0.8)
                            self.log_message.emit(
                                f"[{account.username}] Đã bấm Cầu vận lần {draw_attempt + 1}/5."
                            )
                        ocr_client.tap_ocr_target("close_cau_van")
                        time.sleep(0.8)
                        self.log_message.emit(
                            f"[{account.username}] Đã hoàn tất 5 lần bấm Cầu vận và đóng cửa sổ."
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Không xác nhận được màn hình Cầu vận; "
                            f"không bấm 5 lần để tránh thao tác nhầm. OCR: {fortune_text[:220] or '(trống)'}"
                        )
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Lỗi thao tác Cầu vận quân đoàn: {exc}"
                    )
                    self.task_progress_changed.emit(
                        f"{account.username} - Cầu vận quân đoàn", "failed", 0, 1
                    )

            if self._config.get("clone_quoc_chien"):
                try:
                    self.log_message.emit(
                        f"[{account.username}] Đang mở mục Chiến tranh để tìm Quốc chiến."
                    )
                    ocr_client.tap_ocr_target("chien_tranh")
                    time.sleep(1.5)
                    found_quoc_chien = False
                    for attempt in range(4):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        screen = self._normalize_screen_text(self._screen_text(device))
                        if "quoc chien" in screen or "quoc_chien" in screen:
                            found_quoc_chien = True
                            break
                        self.log_message.emit(
                            f"[{account.username}] Chưa thấy Quốc chiến; kéo màn hình lần {attempt + 1}/3."
                        )
                        # Drag from A to B using the supplied 1920x1080 normalized points.
                        device.shell("input swipe 524 582 1574 564 500")
                        time.sleep(1.2)
                    if found_quoc_chien:
                        self.log_message.emit(
                            f"[{account.username}] Đã tìm thấy mục Quốc chiến qua OCR."
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Không tìm thấy mục Quốc chiến sau khi kéo."
                        )
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Không thể mở/tìm Quốc chiến: {exc}"
                    )
                    break

            # Close the guild panel after all selected guild-related actions,
            # then log out so the next account starts from the login screen.
            logout_ok = True
            if any(self._config.get(key) for key in (
                "clone_guild_check_in", "clone_receive_lucky_bag", "clone_guild_fortune"
            )):
                try:
                    ocr_client.tap_ocr_target("close_quan_doan")
                    time.sleep(0.8)
                    self.log_message.emit(
                        f"[{account.username}] Đã gửi thao tác đóng màn hình quân đoàn."
                    )
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Không bấm được nút đóng quân đoàn: {exc}; "
                        "vẫn tiếp tục quy trình đăng xuất."
                    )

            if self._config.get("clone_logout", True):
                try:
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng theo yêu cầu.")
                        return
                    self.log_message.emit(
                        f"[{account.username}] Mở profile để đăng xuất."
                    )
                    ocr_client.tap_ocr_target("profile_tuy_chon")
                    time.sleep(1)
                    options_text = ""
                    options_found = False
                    for options_attempt in range(10):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        options_text = self._normalize_screen_text(self._screen_text(device))
                        if "tuy chon" in options_text or "thoat game" in options_text:
                            options_found = True
                            break
                        time.sleep(1)
                    if options_found:
                        self.log_message.emit(
                            f"[{account.username}] Đã nhận diện màn hình tùy chọn: "
                            f"{options_text[:180]}"
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Chưa nhận diện được màn hình tùy chọn; "
                            f"vẫn thử bấm nút Thoát game theo tọa độ. OCR: "
                            f"{options_text[:180] or '(trống)'}"
                        )

                    # Use the OCR target when the label is visible; otherwise use
                    # the same saved coordinate as a deliberate fallback.
                    ocr_client.tap_ocr_target("thoat_game")
                    time.sleep(1)
                    confirm_text = ""
                    confirm_found = False
                    for confirm_attempt in range(10):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        confirm_text = self._normalize_screen_text(self._screen_text(device))
                        if any(marker in confirm_text for marker in (
                            "thoat game", "quoc gia", "chua cong"
                        )):
                            confirm_found = True
                            break
                        time.sleep(1)
                    if confirm_found:
                        self.log_message.emit(
                            f"[{account.username}] Đã nhận diện hộp thoại xác nhận thoát: "
                            f"{confirm_text[:180]}"
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Chưa nhận diện được hộp thoại xác nhận; "
                            "vẫn bấm xác nhận theo tọa độ đã lưu."
                        )
                    ocr_client.tap_ocr_target("thoat_game_xac_nhan")
                    time.sleep(1.5)

                    login_screen_found = False
                    login_text = ""
                    for login_attempt in range(30):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        login_text = self._screen_text(device)
                        if self._is_login_screen(login_text):
                            login_screen_found = True
                            break
                        time.sleep(1)
                    if login_screen_found:
                        self.log_message.emit(
                            f"[{account.username}] Đã quay về màn hình đăng nhập; "
                            "sẵn sàng xử lý account tiếp theo."
                        )
                    else:
                        logout_ok = False
                        self.log_message.emit(
                            f"[{account.username}] Không xác nhận được màn hình đăng nhập "
                            f"sau khi thoát game. OCR: "
                            f"{self._normalize_screen_text(login_text)[:180] or '(trống)'}"
                        )
                except Exception as exc:
                    logout_ok = False
                    self.log_message.emit(
                        f"[{account.username}] Lỗi trong quy trình đăng xuất: {exc}"
                    )

            if not logout_ok:
                failed_count += 1
                processed_count += 1
                account_results.append((account.username, "FAILED — đăng xuất không xác nhận được"))
                emit_account_progress(f"FAILED: {account.username}")
                self.task_progress_changed.emit(
                    f"{account.username} - Đăng nhập", "failed", 0, 1
                )
                self.log_message.emit(
                    f"[{account.username}] Dừng vòng lặp Clone để tránh đăng nhập account kế tiếp "
                    "khi game chưa về màn hình đăng nhập."
                )
                break

            success_count += 1
            processed_count += 1
            account_results.append((account.username, "SUCCESS"))
            self.log_message.emit(
                f"[{account.username}] SUCCESS — đăng nhập thành công, profile đã tải "
                f"({success_count} thành công, {failed_count} thất bại)."
            )
            emit_account_progress(f"SUCCESS: {account.username}")
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "done", 1, 1
            )

        self.log_message.emit(
            f"Kết quả Clone: {success_count} thành công, {failed_count} thất bại, "
            f"{max(0, total - processed_count)} chưa xử lý / tổng {total} tài khoản."
        )
        if account_results:
            self.log_message.emit("TỔNG KẾT TỪNG ACCOUNT:")
            for username, result in account_results:
                self.log_message.emit(f"  {username}: {result}")
        processed_names = {username for username, _result in account_results}
        for account in accounts:
            if account.username not in processed_names:
                self.log_message.emit(f"  {account.username}: NOT PROCESSED — chưa chạy")
        if self._config.get("clone_daily_check_in"):
            self.log_message.emit(
                "Lưu ý: điểm danh hằng ngày hiện chưa có thao tác gameplay hoàn chỉnh."
            )
        if self._config.get("clone_guild_check_in"):
            self.log_message.emit(
                "Lưu ý: đã thêm thao tác bấm Báo danh quân đoàn; chưa xác minh được trạng thái nhận thưởng thành công."
            )

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
