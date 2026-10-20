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
                self._replace_focused_text(device, account.password)

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
                f"[{account.username}] Đăng nhập có vẻ thành công; chờ OCR tìm profile 'quan_chuc'."
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
                if "quan chuc" in normalized_profile or "quan_chuc" in normalized_profile:
                    profile_found = True
                    self.log_message.emit(
                        f"[{account.username}] Đã tìm thấy profile qua OCR: 'quan_chuc'."
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

            if index < total:
                self.log_message.emit(
                    "Chưa có luồng đăng xuất an toàn; không thể tự chuyển sang account kế tiếp "
                    "sau khi account hiện tại đã đăng nhập thành công."
                )
                break

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
        if self._config.get("clone_daily_check_in") or self._config.get("clone_guild_check_in") or self._config.get("clone_receive_lucky_bag") or self._config.get("clone_logout"):
            self.log_message.emit(
                "Lưu ý: điểm danh, báo danh quân đoàn, nhận túi phúc và đăng xuất "
                "chưa được triển khai; hiện chỉ thực hiện đăng nhập."
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
