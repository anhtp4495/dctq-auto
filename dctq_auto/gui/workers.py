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

        self.log_message.emit("BƯỚC 1/7: Mở mục Hoạt động từ màn hình chính.")
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

            self.log_message.emit(
                "BƯỚC 2/7: Sau khi mở Hoạt động, chờ 5 giây rồi quét OCR 3 lần; "
                "chỉ khi cả 3 lần đều không thấy nhãn Phúc lợi mới thử 3 vị trí."
            )
            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False
            time.sleep(5.0)
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            phuc_loi_rect = (
                round(14 / 1920 * screen_width),
                round(128 / 1080 * screen_height),
                round(488 / 1920 * screen_width),
                round(988 / 1080 * screen_height),
            )
            phuc_loi_markers = (
                "tranh ba", "qua online", "diem danh",
                "le bao thien", "le bao quoc", "hoan the",
            )

            def phuc_loi_screen_matches() -> tuple[bool, str]:
                detected = self._ocr_words_in_rect(device, phuc_loi_rect)
                detected_text = " ".join(word["text"] for word in detected)
                normalized_text = self._normalize_screen_text(detected_text)
                found = [
                    marker for marker in phuc_loi_markers
                    if marker in normalized_text
                ]
                return bool(found), ", ".join(found) if found else normalized_text[:180]

            phuc_loi_found = False
            initial_ocr = ""
            for ocr_attempt in range(1, 4):
                if not self._wait_if_paused():
                    self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                    return False
                phuc_loi_found, initial_ocr = phuc_loi_screen_matches()
                if phuc_loi_found:
                    self.log_message.emit(
                        f"OCR kiểm tra {ocr_attempt}/3 đã thấy nội dung Phúc lợi "
                        f"({initial_ocr}); không cần click thử button_1/2/3."
                    )
                    break
                self.log_message.emit(
                    f"OCR kiểm tra {ocr_attempt}/3 chưa thấy nhãn Phúc lợi: "
                    f"{initial_ocr!r}"
                )
                if ocr_attempt < 3:
                    time.sleep(1.0)

            if not phuc_loi_found:
                self.log_message.emit(
                    "Cả 3 lần quét OCR đều chưa thấy nhãn Phúc lợi; "
                    "bắt đầu thử 3 vị trí button_1/2/3."
                )
                phuc_loi_candidates = (
                    ("button_1", 143 / 1920, 358 / 1080),
                    ("button_2", 135 / 1920, 495 / 1080),
                    ("button_3", 123 / 1920, 613 / 1080),
                )
                for attempt, (button_name, x_ratio, y_ratio) in enumerate(
                    phuc_loi_candidates, start=1
                ):
                    if not self._wait_if_paused():
                        self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                        return False
                    phuc_loi_x = round(x_ratio * screen_width)
                    phuc_loi_y = round(y_ratio * screen_height)
                    self.log_message.emit(
                        f"Click thử {button_name} ({attempt}/3) tại "
                        f"({phuc_loi_x}, {phuc_loi_y}); chờ 3 giây rồi quét OCR."
                    )
                    device.shell(f"input tap {phuc_loi_x} {phuc_loi_y}")
                    time.sleep(3.0)
                    phuc_loi_found, ocr_result = phuc_loi_screen_matches()
                    if phuc_loi_found:
                        self.log_message.emit(
                            f"Xác định button_phuc_loi là {button_name}; "
                            f"OCR thấy: {ocr_result}."
                        )
                        break
                    self.log_message.emit(
                        f"{button_name} chưa đúng vị trí; OCR chưa thấy nhãn mục "
                        f"Phúc lợi ({attempt}/3): {ocr_result!r}"
                    )
                if not phuc_loi_found:
                    raise RuntimeError(
                        "OCR không thấy nhãn Phúc lợi sau 3 lần quét ban đầu "
                        "và 3 vị trí click thử."
                    )

            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            # Vị trí button_diem_danh nằm ngay phía trên mục Tranh bá.
            tranh_ba_rect = (
                round(0 / 1920 * screen_width),
                round(874 / 1080 * screen_height),
                round(474 / 1920 * screen_width),
                round(1002 / 1080 * screen_height),
            )
            # Dùng đúng vùng Phúc lợi người dùng đã xác định:
            # góc trái-trên (199, 125), góc phải-dưới (471, 995) ở 1920x1080.
            diem_danh_rect = (
                round(199 / 1920 * screen_width),
                round(125 / 1080 * screen_height),
                round(471 / 1920 * screen_width),
                round(995 / 1080 * screen_height),
            )
            activity_rect = diem_danh_rect

            # BƯỚC 3: Nhận lễ bao miễn phí sau khi xác định đúng nút Phúc lợi.
            self.log_message.emit("BƯỚC 3/7: Nhận lễ bao miễn phí.")
            self.log_message.emit("Đã xác định vị trí Phúc lợi; click lễ bao miễn phí.")
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
            # Gửi Enter để đóng/xác nhận dialog lễ bao nếu dialog đang mở.
            device.shell("input keyevent 66")
            self.log_message.emit("Đã gửi phím Enter để đóng/xác nhận dialog lễ bao.")
            time.sleep(0.5)

            self.log_message.emit("BƯỚC 4/7: Tìm nút Điểm danh bằng OCR, thử tối đa 3 lần.")
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

            # RECT bao toàn bộ lưới 36 ô: 4 hàng x 9 cột.
            # Hai góc người dùng cung cấp trên màn hình 1920x1080:
            # trái-trên (484, 402), phải-dưới (1822, 998).
            # Dùng tỷ lệ để tự co giãn theo độ phân giải, sau đó click tâm từng ô.
            calendar_image = device.screenshot()
            calendar_width, calendar_height = calendar_image.size
            rect_left = 484 / 1920
            rect_top = 402 / 1080
            rect_right = 1822 / 1920
            rect_bottom = 998 / 1080
            grid_left = rect_left * calendar_width
            grid_top = rect_top * calendar_height
            grid_width = (rect_right - rect_left) * calendar_width
            grid_height = (rect_bottom - rect_top) * calendar_height

            # Lưới có 30 ô theo cách đánh số người dùng cung cấp:
            # hàng 1: 1-9, hàng 2: 10-18, hàng 3: 19-26, hàng 4: 27-30.
            # Tọa độ mỗi ô lấy theo tâm cột/hàng trong RECT; hàng ngắn hơn
            # được căn trái theo các cột đầu tiên của lưới 9 cột.
            cells_reverse = tuple(range(30, 0, -1))
            if len(cells_reverse) != 30 or set(cells_reverse) != set(range(1, 31)):
                raise RuntimeError("Danh sách ô điểm danh không đủ 30 ô.")

            row_ranges = (
                (1, 9),
                (10, 18),
                (19, 26),
                (27, 30),
            )
            cell_positions = {}
            for row_index, (first_cell, last_cell) in enumerate(row_ranges):
                for cell in range(first_cell, last_cell + 1):
                    column_index = cell - first_cell
                    cell_positions[cell] = (row_index, column_index)

            self.log_message.emit(
                f"BƯỚC 5/6: Lưới điểm danh {calendar_width}x{calendar_height}, "
                f"RECT=({round(grid_left)}, {round(grid_top)}, "
                f"{round(grid_left + grid_width)}, {round(grid_top + grid_height)}); "
                "sẽ click đủ 30/30 ô theo thứ tự 30 → 1."
            )
            for cell in cells_reverse:
                if not self._wait_if_paused():
                    self.log_message.emit(
                        f"Điểm danh đã dừng theo yêu cầu tại ô {cell}."
                    )
                    return False

                row, column = cell_positions[cell]
                day_x = round(grid_left + (column + 0.5) * grid_width / 9)
                day_y = round(grid_top + (row + 0.5) * grid_height / 4)
                device.shell(f"input tap {day_x} {day_y}")
                self.log_message.emit(
                    f"Đã click ô {cell}/30 (hàng {row + 1}, cột {column + 1}) "
                    f"tại ({day_x}, {day_y})."
                )
                time.sleep(0.15)

            self.log_message.emit(
                "Đã chọn xong 30/30 ô; bỏ qua xac_nhan_diem_danh_bu vì không còn cần thiết."
            )
            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu trước khi thoát màn hình.")
                return False
            close_x = round(0.972396 * calendar_width)
            close_y = round(0.119444 * calendar_height)
            self.log_message.emit(
                f"BƯỚC 6/6: Đóng màn hình Điểm danh tại ({close_x}, {close_y})."
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
