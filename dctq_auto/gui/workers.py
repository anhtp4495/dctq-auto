"""Background workers for GUI actions."""

import re
import shlex
import time
import unicodedata
from types import SimpleNamespace
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
        if self._config.get("utility_tasks_mode"):
            selected = []
            if self._config.get("task_login"):
                selected.append("Đăng nhập")
            if self._config.get("diem_danh"):
                selected.append("Điểm danh")
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
            if self._config.get("thiet_lap_muu_binh"):
                selected.append("Mưu binh")
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
                if not self._mock_tick(
                    f"[{account.username}] {label}: chạy thử bước "
                    f"{task_index}/{len(selected)}."
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
    def _normalize_screen_text(text: str) -> str:
        text = unicodedata.normalize("NFD", text.lower())
        text = "".join(
            char for char in text
            if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    @staticmethod
    def _screen_text(device) -> str:
        """Read visible game text using multiple Tesseract layouts for small UI labels."""
        image = ImageOps.autocontrast(device.screenshot().convert("L"))
        recognized: list[str] = []
        for language in ("vie+eng", "eng"):
            language_failed = False
            for page_mode in (6, 11):
                try:
                    text = pytesseract.image_to_string(
                        image, lang=language, config=f"--psm {page_mode}"
                    ).strip()
                except pytesseract.TesseractError:
                    language_failed = True
                    break
                if text and text not in recognized:
                    recognized.append(text)
            if not language_failed and recognized:
                break
        # Combine layout passes so a label missed by block-oriented OCR can still
        # contribute to the conservative login-screen checks.
        return "\\n".join(recognized)

    @staticmethod
    def _tap_ocr_word(device, words: tuple[str, ...]) -> bool:
        """Tap a live OCR word or phrase, including labels split into multiple words."""
        image = ImageOps.autocontrast(device.screenshot().convert("L"))
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
        lines = {}
        total_words = len(data.get("text", []))
        blocks = data.get("block_num", [0] * total_words)
        paragraphs = data.get("par_num", [0] * total_words)
        line_numbers = data.get("line_num", [0] * total_words)
        for i, raw in enumerate(data.get("text", [])):
            normalized = BotWorker._normalize_screen_text(raw)
            if not normalized:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            left, top = int(data["left"][i]), int(data["top"][i])
            width, height = int(data["width"][i]), int(data["height"][i])
            candidates.append((confidence, left, top, width, height, normalized))
            line_key = (blocks[i], paragraphs[i], line_numbers[i])
            lines.setdefault(line_key, []).append(
                (left, top, width, height, confidence, normalized)
            )

        matches = [
            (confidence, left, top, width, height)
            for confidence, left, top, width, height, normalized in candidates
            if normalized in wanted
        ]
        # OCR commonly splits Vietnamese labels such as "Điểm danh" into two words.
        for line_words in lines.values():
            line_words.sort(key=lambda item: item[0])
            for start_index in range(len(line_words)):
                phrase_parts = []
                for end_index in range(start_index, min(len(line_words), start_index + 5)):
                    phrase_parts.append(line_words[end_index][5])
                    if " ".join(phrase_parts) not in wanted:
                        continue
                    selected = line_words[start_index:end_index + 1]
                    left = min(item[0] for item in selected)
                    top = min(item[1] for item in selected)
                    right = max(item[0] + item[2] for item in selected)
                    bottom = max(item[1] + item[3] for item in selected)
                    confidence = sum(item[4] for item in selected) / len(selected)
                    matches.append((confidence, left, top, right - left, bottom - top))

        if not matches:
            return False
        confidence, left, top, width, height = max(matches, key=lambda item: item[0])
        x, y = int(left + width / 2), int(top + height / 2)
        device.shell(f"input tap {x} {y}")
        return True

    @staticmethod
    def _ocr_words_in_rect(device, rect: tuple[int, int, int, int]) -> list[dict]:
        """Recognize words only inside a screenshot rectangle; return full-screen boxes."""
        image = device.screenshot().convert("RGB")
        screen_width, screen_height = image.size
        left, top, right, bottom = rect
        left = max(0, min(screen_width - 1, left))
        top = max(0, min(screen_height - 1, top))
        right = max(left + 1, min(screen_width, right))
        bottom = max(top + 1, min(screen_height, bottom))
        crop = ImageOps.autocontrast(image.crop((left, top, right, bottom)).convert("L"))
        try:
            data = pytesseract.image_to_data(
                crop, lang="vie+eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                crop, lang="eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        words = []
        for i, raw in enumerate(data.get("text", [])):
            normalized = BotWorker._normalize_screen_text(raw)
            if not normalized:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            x = left + int(data["left"][i])
            y = top + int(data["top"][i])
            width = int(data["width"][i])
            height = int(data["height"][i])
            words.append({
                "text": normalized, "confidence": confidence,
                "left": x, "top": y, "width": width, "height": height,
            })
        return words

    @staticmethod
    def _tap_ocr_phrase_in_rect(device, words: tuple[str, ...], rect: tuple[int, int, int, int]) -> bool:
        """Find and tap a word or contiguous phrase inside a specified rectangle."""
        wanted = {BotWorker._normalize_screen_text(word) for word in words}
        detected = BotWorker._ocr_words_in_rect(device, rect)
        matches = [
            word for word in detected if word["text"] in wanted
        ]
        # OCR often separates multi-word Vietnamese labels; join adjacent words on a line.
        image = device.screenshot().convert("RGB")
        screen_width, screen_height = image.size
        left, top, right, bottom = rect
        left, top = max(0, left), max(0, top)
        right, bottom = min(screen_width, right), min(screen_height, bottom)
        crop = ImageOps.autocontrast(image.crop((left, top, right, bottom)).convert("L"))
        try:
            data = pytesseract.image_to_data(
                crop, lang="vie+eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                crop, lang="eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        count = len(data.get("text", []))
        blocks = data.get("block_num", [0] * count)
        paragraphs = data.get("par_num", [0] * count)
        line_numbers = data.get("line_num", [0] * count)
        lines = {}
        for i, raw in enumerate(data.get("text", [])):
            normalized = BotWorker._normalize_screen_text(raw)
            if not normalized:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            x = left + int(data["left"][i])
            y = top + int(data["top"][i])
            width = int(data["width"][i])
            height = int(data["height"][i])
            lines.setdefault((blocks[i], paragraphs[i], line_numbers[i]), []).append(
                (x, y, width, height, confidence, normalized)
            )
        for line in lines.values():
            line.sort(key=lambda item: item[0])
            for start in range(len(line)):
                phrase_parts = []
                for end in range(start, min(len(line), start + 4)):
                    phrase_parts.append(line[end][5])
                    if " ".join(phrase_parts) in wanted:
                        group = line[start:end + 1]
                        x1 = min(item[0] for item in group)
                        y1 = min(item[1] for item in group)
                        x2 = max(item[0] + item[2] for item in group)
                        y2 = max(item[1] + item[3] for item in group)
                        matches.append({
                            "text": " ".join(phrase_parts),
                            "confidence": sum(item[4] for item in group) / len(group),
                            "left": x1, "top": y1,
                            "width": x2 - x1, "height": y2 - y1,
                        })
        if not matches:
            return False
        # Prefer multiword label matches when confidence is comparable.
        match = max(matches, key=lambda item: (item["confidence"], item["width"]))
        x = match["left"] + match["width"] // 2
        y = match["top"] + match["height"] // 2
        device.shell(f"input tap {x} {y}")
        return True

    def _run_daily_checkin(self, device, ocr_client) -> bool:
        """Open Hoạt động, then locate and tap Điểm danh using live OCR."""
        if not self._wait_if_paused():
            self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
            return False

        self.log_message.emit("BƯỚC 1/6: Mở mục Hoạt động từ màn hình chính.")
        try:
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            hoat_dong_x = round(0.035937 * screen_width)
            hoat_dong_y = round(0.732407 * screen_height)
            device.shell(f"input tap {hoat_dong_x} {hoat_dong_y}")
            self.log_message.emit(
                "Đã click button_hoat_dong theo tọa độ tỷ lệ "
                f"({hoat_dong_x}, {hoat_dong_y}); không dùng OCR để click nút này."
            )

            self.log_message.emit("BƯỚC 2/6: Kiểm tra màn hình Hoạt động bằng OCR.")
            screen_text = ""
            normalized = ""
            activity_markers = ("phuc loi", "le bao", "diem danh", "hoat dong")
            for attempt in range(6):
                if not self._wait_if_paused():
                    self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                    return False
                time.sleep(0.7)
                screen_text = self._screen_text(device)
                normalized = self._normalize_screen_text(screen_text)
                matched = [marker for marker in activity_markers if marker in normalized]
                if len(matched) >= 2:
                    self.log_message.emit(
                        "OCR xác nhận màn hình Hoạt động: " + ", ".join(matched)
                    )
                    break
                if attempt == 5:
                    # OCR is unreliable on this game screen and may misread
                    # labels even when the fixed Hoạt động tap succeeded.
                    # Do not abort here; continue the known navigation flow.
                    self.log_message.emit(
                        "OCR chưa xác nhận đủ dấu hiệu màn hình Hoạt động; "
                        "tiếp tục luồng theo tọa độ đã cấu hình. Văn bản OCR: "
                        f"{normalized[:240]!r}"
                    )

            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            # User-provided RECT bounds are normalized to screenshot ratios:
            # x=0..473 / 1920, y=119..996 / 1080.
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            activity_rect = (
                round(0.0 * screen_width),
                round(0.110185 * screen_height),
                round(0.246354 * screen_width),
                round(0.922222 * screen_height),
            )

            # BƯỚC 3: Luôn mở Phúc lợi và nhận lễ bao miễn phí trước khi vào Điểm danh.
            self.log_message.emit("BƯỚC 3/6: Mở Phúc lợi và nhận lễ bao miễn phí.")
            if True:
                phuc_loi_x = round(0.077604 * screen_width)
                phuc_loi_y = round(0.325000 * screen_height)
                self.log_message.emit(
                    "Chưa thấy Điểm danh ở lần OCR xác nhận; click button_phuc_loi "
                    f"tại ({phuc_loi_x}, {phuc_loi_y})."
                )
                device.shell(f"input tap {phuc_loi_x} {phuc_loi_y}")
                self.log_message.emit("Đã click Phúc lợi; click tiếp lễ bao miễn phí.")
                le_bao_x = round(0.366667 * screen_width)
                le_bao_y = round(0.202778 * screen_height)
                device.shell(f"input tap {le_bao_x} {le_bao_y}")
                self.log_message.emit(
                    f"Đã click le_bao_mien_phi tại ({le_bao_x}, {le_bao_y}); chờ 3 giây."
                )
                time.sleep(3.0)
                if not self._wait_if_paused():
                    self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                    return False
            
            self.log_message.emit("BƯỚC 4/6: Tìm nút Điểm danh bằng OCR, thử tối đa 3 lần.")
            clicked_diem_danh = False
            for attempt in range(1, 4):
                if not self._wait_if_paused():
                    self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                    return False
                self.log_message.emit(
                    f"Lần {attempt}/3: tìm và click button_diem_danh trong RECT "
                    f"({activity_rect[0]}, {activity_rect[1]}, "
                    f"{activity_rect[2]}, {activity_rect[3]})."
                )
                if self._tap_ocr_phrase_in_rect(
                    device, ("diem danh",), activity_rect
                ):
                    clicked_diem_danh = True
                    self.log_message.emit(
                        f"Đã click button_diem_danh lần {attempt}/3."
                    )
                    time.sleep(1.0)
                    # The reward-success dialog can remain above the activity
                    # page; retry the button so the game advances to the calendar.
                    if attempt < 3:
                        continue
                    break
                time.sleep(0.7)
            if not clicked_diem_danh:
                raise RuntimeError(
                    "OCR không tìm thấy button_diem_danh trong RECT sau 3 lần thử."
                )
            self.log_message.emit(
                "Đã thử click button_diem_danh tối đa 3 lần; chờ màn hình chọn ngày."
            )
            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            # The calendar is a 9-column grid. Use the measured ratios for
            # days 1-9 and the measured first-column row positions for days
            # 10, 20, and 30. Fill days 11-19 and 21-29 by column/row.
            calendar_image = device.screenshot()
            calendar_width, calendar_height = calendar_image.size
            column_x_ratios = (
                0.290104, 0.364063, 0.446354, 0.502604, 0.590104,
                0.675521, 0.750000, 0.829688, 0.901042,
            )
            first_row_y_ratios = (
                0.443519, 0.469444, 0.435185, 0.459259, 0.462963,
                0.450926, 0.460185, 0.450926, 0.460185,
            )
            row_y_ratios = {
                0: first_row_y_ratios,
                1: (0.580556,) * 9,
                2: (0.725000,) * 9,
            }
            # Keep the measured coordinates for the last row's first 3 cells.
            last_row_ratios = {
                30: (0.288021, 0.858333),
                31: (0.368229, 0.882407),
                32: (0.447917, 0.858333),
            }

            self.log_message.emit(
                f"BƯỚC 5/6: Màn hình chọn ngày {calendar_width}x{calendar_height}; "
                "bắt đầu chọn lần lượt 32 ô ngày."
            )
            for day in range(1, 33):
                if not self._wait_if_paused():
                    self.log_message.emit(
                        f"Điểm danh đã dừng theo yêu cầu tại ngày {day}."
                    )
                    return False

                if day in last_row_ratios:
                    x_ratio, y_ratio = last_row_ratios[day]
                else:
                    row = (day - 1) // 9
                    column = (day - 1) % 9
                    x_ratio = column_x_ratios[column]
                    y_ratio = row_y_ratios[row][column]

                day_x = round(x_ratio * calendar_width)
                day_y = round(y_ratio * calendar_height)
                device.shell(f"input tap {day_x} {day_y}")
                self.log_message.emit(
                    f"Đã click ô ngày {day}/32 tại ({day_x}, {day_y})."
                )
                time.sleep(0.15)

            self.log_message.emit(
                "Đã chọn xong 32/32 ô ngày; chuẩn bị bấm xac_nhan đúng 1 lần."
            )
            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu trước khi xác nhận.")
                return False
            confirm_x = round(0.616667 * calendar_width)
            confirm_y = round(0.631481 * calendar_height)
            self.log_message.emit(
                f"BƯỚC 6/6: Bấm xac_nhan một lần duy nhất tại "
                f"({confirm_x}, {confirm_y})."
            )
            device.shell(f"input tap {confirm_x} {confirm_y}")
            self.log_message.emit("Đã bấm xac_nhan 1/1; chờ game xử lý.")
            time.sleep(0.5)
            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu trước khi thoát màn hình.")
                return False
            close_x = round(0.972396 * calendar_width)
            close_y = round(0.119444 * calendar_height)
            self.log_message.emit(
                f"Đang đóng màn hình Điểm danh tại ({close_x}, {close_y})."
            )
            device.shell(f"input tap {close_x} {close_y}")
            self.log_message.emit("Đã đóng màn hình Điểm danh.")
            time.sleep(0.5)
            return True
        except Exception as exc:
            self.log_message.emit(f"Điểm danh thất bại: {exc}")
            return False

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
            ("diem_danh", "Điểm danh"),
            ("bao_danh_quan_doan", "Báo danh quân đoàn"),
            ("dong_gop_knb", "Đóng góp KNB"),
            ("tham_do_lanh_dia", "Thăm dò lãnh địa"),
            ("nhiem_vu_luu_ly_thap", "Lưu Ly Tháp"),
            ("thuc_hien_giao_tranh", "Giao tranh"),
            ("thuc_hien_tranh_ba", "Tranh bá"),
            ("thiet_lap_muu_binh", "Mưu binh"),
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
            "task_login", "diem_danh", "task_close_guild",
            "task_switch_account", "task_click_coordinates",
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

        if self._config.get("task_close_guild"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            try:
                self.log_message.emit(
                    "Tác vụ: đóng giao diện Quân đoàn bằng tọa độ đã lưu."
                )
                ocr_client.tap_ocr_target("close_quan_doan")
                time.sleep(0.8)
                completed += 1
                self.progress_changed.emit(
                    completed, max(1, total), "Đã gửi thao tác đóng Quân đoàn"
                )
                self.task_progress_changed.emit(
                    "Thoát màn hình Quân đoàn", "done", 1, 1
                )
                self.log_message.emit(
                    "Đã gửi thao tác đóng giao diện Quân đoàn. "
                    "Đây không phải thao tác rời bang hội."
                )
            except Exception as exc:
                self.log_message.emit(
                    f"Không đóng được giao diện Quân đoàn: {exc}"
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
