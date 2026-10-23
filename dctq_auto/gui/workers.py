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
    def _normalize_screen_text(text: str) -> str:
        text = unicodedata.normalize("NFD", text.lower())
        text = "".join(
            char for char in text
            if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    @staticmethod
    def _normalize_ocr_match_text(text: str) -> str:
        """Normalize OCR text to lowercase ASCII letters/digits only."""
        normalized = unicodedata.normalize("NFD", text.lower())
        normalized = "".join(
            char for char in normalized
            if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        return re.sub(r"[^a-z0-9]", "", normalized)

    @staticmethod
    def _fuzzy_ocr_target_match(
        recognized_text: str,
        target_text: str,
        threshold: float = 0.25,
    ) -> bool:
        """Match a target against any OCR substring when similarity is above 25% by default."""
        from difflib import SequenceMatcher

        target = BotWorker._normalize_ocr_match_text(target_text)
        recognized = BotWorker._normalize_ocr_match_text(recognized_text)
        if not target or not recognized:
            return False
        if target in recognized:
            return True

        # Partial matching: OCR often appends adjacent labels/noise to the target.
        # Compare windows close to the target length so surrounding text does not
        # reduce the score of an otherwise recognizable label.
        min_len = max(1, int(len(target) * threshold))
        max_len = min(len(recognized), len(target) + max(2, int(len(target) * 0.5)))
        for window_len in range(min_len, max_len + 1):
            for start in range(0, len(recognized) - window_len + 1):
                candidate = recognized[start:start + window_len]
                score = SequenceMatcher(None, target, candidate).ratio()
                if score > threshold:
                    return True
        return False

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
    def _screen_text_in_rect(device, rect: tuple[int, int, int, int]) -> str:
        """OCR only the supplied (left, top, right, bottom) screenshot rectangle."""
        left, top, right, bottom = rect
        image = device.screenshot().convert("RGB")
        width, height = image.size
        left = max(0, min(int(left), width - 1))
        top = max(0, min(int(top), height - 1))
        right = max(left + 1, min(int(right), width))
        bottom = max(top + 1, min(int(bottom), height))
        cropped = ImageOps.autocontrast(image.crop((left, top, right, bottom)).convert("L"))
        recognized: list[str] = []
        for language in ("vie+eng", "eng"):
            language_failed = False
            for page_mode in (6, 11):
                try:
                    text = pytesseract.image_to_string(
                        cropped, lang=language, config=f"--psm {page_mode}"
                    ).strip()
                except pytesseract.TesseractError:
                    language_failed = True
                    break
                if text and text not in recognized:
                    recognized.append(text)
            if not language_failed and recognized:
                break
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

    def _tap_fuzzy_ocr_target(
        self, device, target_text: str, threshold: float = 0.25,
        *, tap: bool = True,
    ) -> tuple[int, int] | None:
        """Find the best OCR word-window for a target; optionally tap its center."""
        from difflib import SequenceMatcher

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

        target = self._normalize_ocr_match_text(target_text)
        if not target:
            return None
        count = len(data.get("text", []))
        lines = {}
        for i, raw in enumerate(data.get("text", [])):
            normalized = self._normalize_ocr_match_text(raw)
            if not normalized:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            key = (
                data.get("block_num", [0] * count)[i],
                data.get("par_num", [0] * count)[i],
                data.get("line_num", [0] * count)[i],
            )
            lines.setdefault(key, []).append((
                int(data["left"][i]), int(data["top"][i]),
                int(data["width"][i]), int(data["height"][i]),
                confidence, normalized,
            ))

        best = None
        for line in lines.values():
            line.sort(key=lambda item: item[0])
            for start in range(len(line)):
                parts = []
                for end in range(start, min(len(line), start + 12)):
                    parts.append(line[end][5])
                    candidate = "".join(parts)
                    score = SequenceMatcher(None, target, candidate).ratio()
                    if score > threshold and (best is None or score > best[0]):
                        group = line[start:end + 1]
                        left = min(item[0] for item in group)
                        top = min(item[1] for item in group)
                        right = max(item[0] + item[2] for item in group)
                        bottom = max(item[1] + item[3] for item in group)
                        best = (score, left, top, right, bottom)
        if best is None:
            return None
        _score, left, top, right, bottom = best
        x, y = round((left + right) / 2), round((top + bottom) / 2)
        if tap:
            device.shell(f"input tap {x} {y}")
        return x, y

    def _run_enter_guild(self, device, ocr_client) -> bool:
        """Open guild chat, click its entry button, then verify the guild screen."""
        try:
            if not self._wait_if_paused():
                return False

            import json

            regions_path = Path(__file__).resolve().parents[1] / "tasks" / "common" / "regions.json"
            try:
                regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Không đọc được {regions_path}: {exc}") from exc

            targets = {}
            for region_data in regions_data.get("regions", {}).values():
                for element in region_data.get("elements", []):
                    name = element.get("name")
                    if name in ("open_chat_quan_doan", "vao_quan_doan"):
                        targets[name] = element

            for required in ("open_chat_quan_doan", "vao_quan_doan"):
                if required not in targets:
                    raise RuntimeError(
                        f"Không tìm thấy '{required}' trong {regions_path}."
                    )

            def target_center(element, width, height):
                center_ratio = element.get("center_ratio", {})
                center = element.get("center", {})
                if "x" in center_ratio and "y" in center_ratio:
                    return (
                        round(float(center_ratio["x"]) * width),
                        round(float(center_ratio["y"]) * height),
                    )
                base_width, base_height = regions_data.get(
                    "reference_resolution", [1920, 1080]
                )
                if "x_px" in center and "y_px" in center:
                    return (
                        round(float(center["x_px"]) / base_width * width),
                        round(float(center["y_px"]) / base_height * height),
                    )
                rect = element.get("rect", {})
                return (
                    round((float(rect.get("x", 0)) + float(rect.get("width", 0)) / 2)
                          / base_width * width),
                    round((float(rect.get("y", 0)) + float(rect.get("height", 0)) / 2)
                          / base_height * height),
                )

            def color_text_ocr(rect_ref, tolerance):
                image = device.screenshot().convert("RGB")
                width, height = image.size
                left = round(rect_ref[0] / 1920 * width)
                top = round(rect_ref[1] / 1080 * height)
                right = round(rect_ref[2] / 1920 * width)
                bottom = round(rect_ref[3] / 1080 * height)
                crop = np.asarray(image.crop((left, top, right, bottom)))
                if crop.size == 0:
                    raise RuntimeError(f"RECT OCR nằm ngoài màn hình: {(left, top, right, bottom)}")
                lab = cv2.cvtColor(crop, cv2.COLOR_RGB2LAB).astype(np.float32)
                white = cv2.cvtColor(
                    np.uint8([[[255, 255, 255]]]), cv2.COLOR_RGB2LAB
                )[0, 0].astype(np.float32)
                black = cv2.cvtColor(
                    np.uint8([[[0, 0, 0]]]), cv2.COLOR_RGB2LAB
                )[0, 0].astype(np.float32)
                white_distance = np.linalg.norm(lab - white, axis=2)
                black_distance = np.linalg.norm(lab - black, axis=2)
                mask = (white_distance <= tolerance) & (white_distance < black_distance)
                processed = np.where(mask, 0, 255).astype(np.uint8)
                processed = cv2.resize(
                    processed, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST
                )
                processed = cv2.copyMakeBorder(
                    processed, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255
                )
                try:
                    text = pytesseract.image_to_string(
                        processed, lang="vie+eng", config="--oem 3 --psm 11"
                    ).strip()
                except pytesseract.TesseractError:
                    text = pytesseract.image_to_string(
                        processed, lang="eng", config="--oem 3 --psm 11"
                    ).strip()
                return text, (left, top, right, bottom), (width, height)

            def matches_marker(text, marker):
                # Avoid the old 25% substring matcher: short accidental fragments
                # such as "Dự tru" could otherwise falsely confirm the guild screen.
                from difflib import SequenceMatcher

                normalized_text = self._normalize_ocr_match_text(text)
                normalized_marker = self._normalize_ocr_match_text(marker)
                if not normalized_text or not normalized_marker:
                    return False
                if normalized_marker in normalized_text:
                    return True
                words = self._normalize_screen_text(text).split()
                for start_index in range(len(words)):
                    for count in range(1, min(4, len(words) - start_index) + 1):
                        candidate = "".join(words[start_index:start_index + count])
                        if len(candidate) < len(normalized_marker) * 0.72:
                            continue
                        if SequenceMatcher(None, normalized_marker, candidate).ratio() >= 0.72:
                            return True
                return False

            # BƯỚC 1: open chat button is loaded from regions.json.
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            click_x, click_y = target_center(
                targets["open_chat_quan_doan"], screen_width, screen_height
            )
            self.log_message.emit(
                "Vào quân đoàn — BƯỚC 1: click open_chat_quan_doan lấy từ regions.json "
                f"tại ({click_x}, {click_y}) trên màn hình {screen_width}x{screen_height}."
            )
            device.shell(f"input tap {click_x} {click_y}")
            time.sleep(1.0)

            if not self._wait_if_paused():
                return False

            # BƯỚC 2: confirm the entry button exists before clicking it.
            recognized_button, button_rect, (screen_width, screen_height) = color_text_ocr(
                (1270, 968, 1532, 1026), 100.0
            )
            self.log_message.emit(
                "Vào quân đoàn — BƯỚC 2: OCR nút vao_quan_doan trong RECT "
                f"{button_rect}; nội dung OCR: {recognized_button or '(trống)'}"
            )
            if not matches_marker(recognized_button, "vao_quan_doan"):
                raise RuntimeError(
                    "Không thấy chính xác nhãn 'Vào quân đoàn' trong vùng nút; "
                    f"không click để tránh thao tác nhầm. OCR: {recognized_button or '(trống)'}"
                )

            click_x, click_y = target_center(
                targets["vao_quan_doan"], screen_width, screen_height
            )
            self.log_message.emit(
                "Đã xác nhận nhãn 'Vào quân đoàn'; click vao_quan_doan lấy từ "
                f"regions.json tại ({click_x}, {click_y}) trên màn hình "
                f"{screen_width}x{screen_height}."
            )
            device.shell(f"input tap {click_x} {click_y}")
            time.sleep(1.5)

            if not self._wait_if_paused():
                return False

            # BƯỚC 3: verify a real guild-screen label, not a loose 25% fragment.
            recognized_header, header_rect, _ = color_text_ocr(
                (147, 4, 956, 147), 38.0
            )
            header_targets = ("quan_doan", "thanh_vien", "tim_quan_doan")
            matched_header = next(
                (candidate for candidate in header_targets
                 if matches_marker(recognized_header, candidate)),
                None,
            )
            self.log_message.emit(
                "Vào quân đoàn — BƯỚC 3: OCR giao diện trong RECT "
                f"{header_rect}; nội dung OCR: {recognized_header or '(trống)'}"
            )
            if not matched_header:
                raise RuntimeError(
                    "Đã click 'Vào quân đoàn' nhưng OCR không nhận diện được nhãn "
                    "giao diện Quân đoàn (cần quan_doan / thanh_vien / tim_quan_doan). "
                    f"OCR: {recognized_header or '(trống)'}"
                )

            self.log_message.emit(
                f"Đã xác nhận giao diện Quân đoàn bằng nhãn '{matched_header}'."
            )
            return True
        except Exception as exc:
            self.log_message.emit(f"Vào quân đoàn thất bại, dừng luồng: {exc}")
            return False

    def _activity_phuc_loi_visible(self, device) -> tuple[bool, str]:
        """Return whether OCR can identify the Hoạt động > Phúc lợi screen."""
        screenshot = device.screenshot()
        screen_width, screen_height = screenshot.size
        phuc_loi_rect = (
            round(14 / 1920 * screen_width),
            round(128 / 1080 * screen_height),
            round(488 / 1920 * screen_width),
            round(988 / 1080 * screen_height),
        )
        detected = self._ocr_words_in_rect(device, phuc_loi_rect)
        detected_text = " ".join(word["text"] for word in detected)
        markers = ("tranh ba", "qua online", "diem danh", "hoan the")
        normalized = self._normalize_screen_text(detected_text)
        return any(self._normalize_screen_text(marker) in normalized for marker in markers), detected_text

    def _run_open_activity(self, device) -> bool:
        """Open Hoạt động only when OCR does not already show its Phúc lợi screen."""
        try:
            if not self._wait_if_paused():
                return False
            visible, detected_text = self._activity_phuc_loi_visible(device)
            if visible:
                self.log_message.emit("Hoạt động đã mở sẵn; không click mở lần nữa.")
                return True
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            x = round(0.035937 * screen_width)
            y = round(0.732407 * screen_height)
            self.log_message.emit(f"Mở màn hình Hoạt động tại ({x}, {y}).")
            device.shell(f"input tap {x} {y}")
            time.sleep(3.0)
            visible, detected_text = self._activity_phuc_loi_visible(device)
            if not visible:
                raise RuntimeError(
                    "OCR chưa xác nhận được màn hình Phúc lợi: "
                    f"{detected_text[:180] or '(trống)'}"
                )
            self.log_message.emit("Đã xác nhận mở màn hình Hoạt động > Phúc lợi.")
            return True
        except Exception as exc:
            self.log_message.emit(f"Mở màn hình Hoạt động thất bại: {exc}")
            return False

    def _run_select_phuc_loi(self, device) -> bool:
        """Select Phúc Lợi by OCR after ensuring Hoạt động is open."""
        try:
            if not self._wait_if_paused():
                return False
            visible, detected_text = self._activity_phuc_loi_visible(device)
            if visible:
                self.log_message.emit("Đã ở mục Phúc Lợi; không cần chọn lại.")
                return True
            if not self._run_open_activity(device):
                return False
            time.sleep(1.0)
            if not self._wait_if_paused():
                return False
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            full_rect = (0, 0, screen_width, screen_height)
            self.log_message.emit("Tìm và chọn mục Phúc Lợi bằng OCR.")
            if not self._tap_ocr_phrase_in_rect(device, ("phuc loi",), full_rect):
                raise RuntimeError("OCR không tìm thấy mục Phúc Lợi để chọn.")
            time.sleep(2.0)
            visible, detected_text = self._activity_phuc_loi_visible(device)
            if not visible:
                raise RuntimeError(
                    "Đã click Phúc Lợi nhưng OCR chưa xác nhận được màn hình Phúc Lợi: "
                    f"{detected_text[:180] or '(trống)'}"
                )
            self.log_message.emit("Đã chọn và xác nhận mục Phúc Lợi.")
            return True
        except Exception as exc:
            self.log_message.emit(f"Chọn Phúc Lợi thất bại: {exc}")
            return False

    def _run_close_activity(self, device) -> bool:
        """Close Hoạt động and verify closure using the Quan chức profile marker."""
        try:
            retries = 2

            def profile_marker_found() -> tuple[bool, str]:
                screenshot = device.screenshot()
                screen_width, screen_height = screenshot.size
                profile_rect = (
                    0,
                    0,
                    max(1, round(200 / 1920 * screen_width)),
                    max(1, round(200 / 1080 * screen_height)),
                )
                detected_text = self._screen_text_in_rect(device, profile_rect)
                normalized = self._normalize_screen_text(detected_text)
                return "quan chuc" in normalized, detected_text

            while True:
                if not self._wait_if_paused():
                    return False

                # Step 1: the profile marker means Hoạt động is already closed.
                profile_found, detected_text = profile_marker_found()
                if profile_found:
                    self.log_message.emit(
                        "OCR tìm thấy 'Quan chức'; xác nhận màn hình Hoạt Động đã đóng."
                    )
                    return True

                # Step 2: retry counter represents remaining Back presses.
                if retries == 0:
                    raise RuntimeError(
                        "Đã hết 2 lần nhấn Back nhưng OCR vẫn không tìm thấy "
                        f"'Quan chức'. Nội dung OCR: {detected_text[:180] or '(trống)'}"
                    )

                self.log_message.emit(
                    f"OCR chưa tìm thấy 'Quan chức'; còn {retries} lượt nhấn Back."
                )

                # Step 3: close the current screen and wait for it to transition.
                device.shell("input keyevent KEYCODE_BACK")
                time.sleep(1.5)

                # Step 4: decrement and return to Step 1 for verification.
                retries -= 1
        except Exception as exc:
            self.log_message.emit(f"Tắt màn hình Hoạt Động thất bại: {exc}")
            return False

    def _run_receive_quoc_van(self, device, ocr_client) -> bool:
        """Receive the free Quốc vận gift and verify that its dialog has closed."""
        target_title = "mua_tich_luy_10_ngay_nhan_them_qua"
        try:
            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 1: Kiểm tra màn hình Hoạt động > Phúc lợi."
            )
            visible, detected_text = self._activity_phuc_loi_visible(device)
            if not visible:
                self.log_message.emit(
                    "Chưa ở màn hình Phúc lợi; mở Hoạt động trước khi tiếp tục."
                )
                if not self._run_open_activity(device):
                    return False
                time.sleep(2.0)
                visible, detected_text = self._activity_phuc_loi_visible(device)
            if not visible:
                raise RuntimeError(
                    "OCR không xác nhận được cac_tinh_nang của hoat_dong.phuc_loi. "
                    f"OCR: {detected_text[:180] or '(trống)'}"
                )

            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 2: OCR xác nhận các tính năng của hoat_dong.phuc_loi."
            )

            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 3: Tìm và click mục Lễ bao Quốc vận bằng OCR."
            )
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            full_rect = (0, 0, screen_width, screen_height)
            if not self._tap_ocr_phrase_in_rect(
                device, ("le bao quoc van",), full_rect
            ):
                self.log_message.emit(
                    "Không tìm thấy mục Lễ bao Quốc vận bằng OCR; bỏ qua tác vụ này."
                )
                return False

            time.sleep(1.2)
            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 4: OCR tìm text chuẩn, yêu cầu tương đồng > 25%."
            )
            screen_text = self._screen_text(device)
            if not self._fuzzy_ocr_target_match(screen_text, target_title, 0.25):
                self.log_message.emit(
                    "OCR không khớp text chuẩn trên 25%; bỏ qua tác vụ Lễ bao Quốc vận. "
                    f"OCR nhận diện được: {screen_text[:220] or '(trống)'}"
                )
                return False

            self.log_message.emit(
                "OCR khớp text chuẩn (>25%): "
                f"{target_title}"
            )
            title_position = self._tap_fuzzy_ocr_target(
                device, target_title, 0.25, tap=False
            )
            if title_position is None:
                raise RuntimeError(
                    "Text OCR đạt ngưỡng nhưng không lấy được vị trí để click xác nhận."
                )

            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 5: Click nút nhan_le_bao_mien_phi tại tọa độ (688; 234)."
            )
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            # Tọa độ gốc theo màn hình 1920x1080, scale theo độ phân giải hiện tại.
            button_x = round(688 / 1920 * screen_width)
            button_y = round(234 / 1080 * screen_height)
            device.shell(f"input tap {button_x} {button_y}")
            time.sleep(1.0)

            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 6: Click tọa độ đóng/xác nhận dialog (728; 867)."
            )
            # Tọa độ đóng/xác nhận dialog theo màn hình gốc 1920x1080.
            close_x = round(728 / 1920 * screen_width)
            close_y = round(867 / 1080 * screen_height)
            device.shell(f"input tap {close_x} {close_y}")
            time.sleep(1.0)

            if not self._wait_if_paused():
                return False

            self.log_message.emit(
                "Lễ bao Quốc vận — kiểm tra lại OCR: text chuẩn phải tương đồng > 25%."
            )
            after_text = self._screen_text(device)
            if not self._fuzzy_ocr_target_match(after_text, target_title, 0.25):
                raise RuntimeError(
                    "Chưa xác nhận nhận lễ bao thành công: sau click + ENTER, "
                    "text chuẩn chưa đạt tương đồng > 25%; "
                    f"OCR: {after_text[:220] or '(trống)'}"
                )

            self.log_message.emit(
                "Đã xác nhận nhận lễ bao Quốc vận thành công: OCR tìm lại được "
                "mua_tich_luy_10_ngay_nhan_them_qua (>25%), dialog đã tắt."
            )
            return True
        except Exception as exc:
            self.log_message.emit(
                f"Nhận lễ bao Quốc vận thất bại; bỏ qua tác vụ này và tiếp tục các tác vụ tiếp theo (không retry): {exc}"
            )
            return False

    def _run_daily_checkin(self, device, ocr_client) -> bool:
        """Open Hoạt động > Phúc lợi > Điểm danh and tap days 30 through 1 once."""
        try:
            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            self.log_message.emit(
                "BƯỚC 1/5: Kiểm tra có đang ở màn hình Hoạt động > Phúc lợi hay chưa."
            )
            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            phuc_loi_rect = (
                round(14 / 1920 * screen_width),
                round(128 / 1080 * screen_height),
                round(488 / 1920 * screen_width),
                round(988 / 1080 * screen_height),
            )
            phuc_loi_markers = ("tranh ba", "qua online", "diem danh", "hoan the")
            detected = self._ocr_words_in_rect(device, phuc_loi_rect)
            detected_text = self._normalize_screen_text(
                " ".join(word["text"] for word in detected)
            )
            already_in_phuc_loi = any(
                marker in detected_text for marker in phuc_loi_markers
            )

            # Nhận lễ bao Quốc vận cũng kết thúc tại màn hình Phúc lợi.
            # Nếu đang ở đây thì không click Hoạt động lần nữa, tránh lệch màn hình.
            if already_in_phuc_loi:
                self.log_message.emit(
                    "Đã nhận diện màn hình Phúc lợi hiện tại; tiếp tục tìm Điểm danh."
                )
            else:
                self.log_message.emit(
                    "Chưa ở màn hình Phúc lợi; mở Hoạt động từ màn hình chính."
                )
                hoat_dong_x = round(0.035937 * screen_width)
                hoat_dong_y = round(0.732407 * screen_height)
                device.shell(f"input tap {hoat_dong_x} {hoat_dong_y}")
                time.sleep(5.0)

                if not self._wait_if_paused():
                    self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                    return False

                self.log_message.emit(
                    "BƯỚC 2/5: Xác nhận màn hình Phúc lợi bằng OCR."
                )
                screenshot = device.screenshot()
                screen_width, screen_height = screenshot.size
                phuc_loi_rect = (
                    round(14 / 1920 * screen_width),
                    round(128 / 1080 * screen_height),
                    round(488 / 1920 * screen_width),
                    round(988 / 1080 * screen_height),
                )
                detected = self._ocr_words_in_rect(device, phuc_loi_rect)
                detected_text = self._normalize_screen_text(
                    " ".join(word["text"] for word in detected)
                )
                if not any(marker in detected_text for marker in phuc_loi_markers):
                    raise RuntimeError(
                        "Không nhận diện được màn hình Phúc lợi; "
                        f"dừng flow. OCR: {detected_text[:180] or '(trống)'}"
                    )

            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            self.log_message.emit("BƯỚC 3/5: Click Điểm danh bằng OCR đúng một lần.")
            diem_danh_rect = (
                round(201 / 1920 * screen_width),
                round(726 / 1080 * screen_height),
                round(474 / 1920 * screen_width),
                round(871 / 1080 * screen_height),
            )
            if not self._tap_ocr_phrase_in_rect(device, ("diem danh",), diem_danh_rect):
                raise RuntimeError(
                    "OCR không tìm thấy nút Điểm danh trong RECT đã cấu hình; "
                    "không retry và không click fallback."
                )
            time.sleep(1.0)

            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            self.log_message.emit("BƯỚC 4/5: Click 30 ô theo thứ tự ngày 30 → ngày 1.")
            calendar_image = device.screenshot()
            calendar_width, calendar_height = calendar_image.size
            grid_left = (484 / 1920) * calendar_width
            grid_top = (402 / 1080) * calendar_height
            grid_width = ((1822 - 484) / 1920) * calendar_width
            grid_height = ((998 - 402) / 1080) * calendar_height

            cells_reverse = tuple(range(30, 0, -1))
            row_ranges = ((1, 9), (10, 18), (19, 26), (27, 30))
            cell_positions = {}
            for row_index, (first_cell, last_cell) in enumerate(row_ranges):
                for cell in range(first_cell, last_cell + 1):
                    cell_positions[cell] = (row_index, cell - first_cell)

            for cell in cells_reverse:
                if not self._wait_if_paused():
                    self.log_message.emit(f"Điểm danh đã dừng theo yêu cầu tại ô {cell}.")
                    return False
                row, column = cell_positions[cell]
                day_x = round(grid_left + (column + 0.5) * grid_width / 9)
                day_y = round(grid_top + (row + 0.5) * grid_height / 4)
                # Mỗi ô chỉ gửi đúng một lệnh tap; lỗi thì dừng, không thử lại.
                device.shell(f"input tap {day_x} {day_y}")
                self.log_message.emit(
                    f"Đã click ô ngày {cell} (hàng {row + 1}, cột {column + 1}) "
                    f"tại ({day_x}, {day_y})."
                )
                time.sleep(0.15)

            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu trước khi đóng màn hình.")
                return False

            self.log_message.emit("BƯỚC 5/5: Đóng màn hình Điểm danh.")
            close_x = round(0.972396 * calendar_width)
            close_y = round(0.119444 * calendar_height)
            device.shell(f"input tap {close_x} {close_y}")
            time.sleep(0.5)
            self.log_message.emit("Đã hoàn tất flow Điểm danh: click đủ 30 ô từ ngày 30 đến ngày 1.")
            return True
        except Exception as exc:
            self.log_message.emit(f"Điểm danh thất bại, dừng ngay (không retry): {exc}")
            return False

    def _ensure_guild_screen(self, device, task_label: str) -> str:
        """Only run guild actions when OCR confirms the guild screen is already open."""
        screen_text = self._normalize_screen_text(self._screen_text(device))
        trusted_markers = (
            "thanh vien",
            "tim quan doan",
            "doan truong",
            "doan pho",
            "quan su",
            "tinh anh",
            "toi can tang vien",
        )
        if not any(marker in screen_text for marker in trusted_markers):
            raise RuntimeError(
                f"Chưa xác nhận màn hình Quân đoàn; không thao tác '{task_label}'. "
                f"OCR: {screen_text[:220] or '(trống)'}"
            )
        self.log_message.emit(
            f"{task_label}: đã xác nhận màn hình Quân đoàn bằng OCR: {screen_text[:180]}"
        )
        return screen_text

    def _run_guild_screen_task(self, task_key: str, device, ocr_client) -> bool:
        """Run one guild action without opening or closing the guild screen itself."""
        task_labels = {
            "bao_danh_quan_doan": "Báo danh quân đoàn",
            "task_receive_lucky_bag": "Nhận túi phúc",
            "task_guild_fortune": "Cầu vận quân đoàn (5 lần)",
        }
        label = task_labels[task_key]
        self.task_progress_changed.emit(label, "running", 0, 1)
        try:
            if not self._wait_if_paused():
                self.log_message.emit(f"{label}: đã dừng theo yêu cầu.")
                return False

            self._ensure_guild_screen(device, label)

            if task_key == "bao_danh_quan_doan":
                self.log_message.emit(
                    "Báo danh quân đoàn — click bao_danh_nhan_thuong từ regions.json."
                )
                x, y = ocr_client.tap_ocr_target("bao_danh_nhan_thuong")
                time.sleep(1.5)
                if not self._wait_if_paused():
                    self.log_message.emit("Báo danh quân đoàn đã dừng theo yêu cầu.")
                    return False
                after_text = self._normalize_screen_text(self._screen_text(device))
                self.log_message.emit(
                    f"Đã click Báo danh nhận thưởng tại ({x}, {y}). "
                    "Thao tác đã gửi; OCR sau click (không tự suy diễn trạng thái nhận thưởng): "
                    f"{after_text[:220] or '(trống)'}"
                )

            elif task_key == "task_receive_lucky_bag":
                self.log_message.emit(
                    "Nhận túi phúc — mở mục tui_phuc theo tọa độ đã lưu trong regions.json."
                )
                ocr_client.tap_ocr_target("tui_phuc")
                time.sleep(1.2)
                bag_text = ""
                bag_screen_found = False
                bag_markers = (
                    "tui phuc tuong",
                    "tui phuc truong thanh",
                    "tui phuc knb",
                    "co so",
                )
                for attempt in range(5):
                    if not self._wait_if_paused():
                        self.log_message.emit("Nhận túi phúc đã dừng theo yêu cầu.")
                        return False
                    bag_text = self._normalize_screen_text(self._screen_text(device))
                    if any(marker in bag_text for marker in bag_markers):
                        bag_screen_found = True
                        break
                    if attempt < 4:
                        time.sleep(1)
                if not bag_screen_found:
                    raise RuntimeError(
                        "Đã mở mục Túi phúc nhưng OCR chưa xác nhận được màn hình Túi phúc; "
                        f"không click các nút nhận. OCR: {bag_text[:220] or '(trống)'}"
                    )

                self.log_message.emit(
                    f"Đã xác nhận màn hình Túi phúc: {bag_text[:180]}"
                )
                for target in ("tui_phuc_thuong", "tui_phuc_truong_thanh", "tui_phuc_knb"):
                    if not self._wait_if_paused():
                        self.log_message.emit("Nhận túi phúc đã dừng theo yêu cầu.")
                        return False
                    x, y = ocr_client.tap_ocr_target(target)
                    self.log_message.emit(
                        f"Đã click {target} theo regions.json tại ({x}, {y})."
                    )
                    time.sleep(1)
                if not self._wait_if_paused():
                    self.log_message.emit("Nhận túi phúc đã dừng trước khi đóng cửa sổ.")
                    return False

                # A reward click may open a second-level detail dialog. Close it
                # only when its title is OCR-confirmed, then OCR again before
                # deciding whether the main Túi phúc window can be closed.
                bag_rect = (147, 4, 1809, 172)
                detail_title = "chi_tiet_nhan_tui_phuc_knb_hom_nay"
                main_window_markers = ("tui_phuc", "gui_tui_phuc", "cuop_tui_phuc")
                visible_text = self._screen_text_in_rect(device, bag_rect)
                self.log_message.emit(
                    f"Nhận túi phúc — OCR RECT man_hinh_tui_phuc {bag_rect}: "
                    f"{visible_text[:220] or '(trống)'}"
                )

                if self._fuzzy_ocr_target_match(
                    visible_text, detail_title, threshold=0.5
                ):
                    self.log_message.emit(
                        "OCR khớp chi_tiet_nhan_tui_phuc_knb_hom_nay > 50%; "
                        "đóng chi tiết bằng tọa độ dong_chi_tiet_tui_phuc."
                    )
                    ocr_client.tap_ocr_target("dong_chi_tiet_tui_phuc")
                    time.sleep(0.8)
                    visible_text = self._screen_text_in_rect(device, bag_rect)
                    self.log_message.emit(
                        f"OCR lại sau khi đóng chi tiết: "
                        f"{visible_text[:220] or '(trống)'}"
                    )

                normalized_bag_text = self._normalize_screen_text(visible_text)
                matched_main_marker = next(
                    (
                        marker for marker in main_window_markers
                        if self._fuzzy_ocr_target_match(
                            normalized_bag_text, marker, threshold=0.5
                        )
                    ),
                    None,
                )
                if not matched_main_marker:
                    raise RuntimeError(
                        "Nhận túi phúc thất bại: đã không xác nhận được cửa sổ chính "
                        "bằng OCR sau khi đóng chi tiết (cần tui_phuc, gui_tui_phuc "
                        "hoặc cuop_tui_phuc); không click nút đóng cửa sổ chính. "
                        f"OCR: {visible_text[:220] or '(trống)'}"
                    )

                if not self._wait_if_paused():
                    self.log_message.emit("Nhận túi phúc đã dừng trước khi đóng cửa sổ chính.")
                    return False
                self.log_message.emit(
                    f"OCR xác nhận cửa sổ Túi phúc qua '{matched_main_marker}'; "
                    "đóng bằng tọa độ dong_man_hinh_tui_phuc."
                )
                ocr_client.tap_ocr_target("dong_man_hinh_tui_phuc")
                time.sleep(0.8)
                self.log_message.emit(
                    "Đã xử lý 3 mục Túi phúc và đóng đúng cửa sổ đã được OCR xác nhận; "
                    "không đóng màn hình Quân đoàn."
                )

            elif task_key == "task_guild_fortune":
                from dctq_auto.tasks.common.guild_logistics import run_guild_logistics

                account = SimpleNamespace(username="Tác vụ")
                if not run_guild_logistics(self, account, device, ocr_client):
                    raise RuntimeError(
                        "Không hoàn tất được Cầu vận; xem nhật ký OCR ở phía trên."
                    )

            self.task_progress_changed.emit(label, "done", 1, 1)
            self.log_message.emit(
                f"Hoàn tất tác vụ '{label}'. Màn hình Quân đoàn vẫn được giữ nguyên."
            )
            return True
        except Exception as exc:
            self.log_message.emit(f"{label} thất bại: {exc}")
            self.task_progress_changed.emit(label, "failed", 0, 1)
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


    @staticmethod
    def _strategy_regions():
        """Load Mưu Binh coordinates from regions.json and reject placeholders."""
        import json

        path = Path(__file__).resolve().parents[1] / "tasks" / "common" / "regions.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Không đọc được regions.json: {exc}") from exc
        section = data.get("regions", {}).get("muu_binh", {})
        elements = {
            item.get("name"): item
            for item in section.get("elements", [])
            if isinstance(item, dict) and item.get("name")
        }
        return path, elements

    @staticmethod
    def _strategy_point(elements, name):
        item = elements.get(name, {})
        center = item.get("center", {})
        x, y = center.get("x_px"), center.get("y_px")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        if (int(x), int(y)) == (1, 1) or int(x) < 2 or int(y) < 2:
            return None
        return int(x), int(y)

    @staticmethod
    def _strategy_rect(elements, name):
        item = elements.get(name, {})
        bounds = item.get("bounds", {})
        try:
            left, top, right, bottom = (
                int(bounds["left"]), int(bounds["top"]),
                int(bounds["right"]), int(bounds["bottom"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if left < 0 or top < 0 or right <= left or bottom <= top:
            return None
        if (left, top, right, bottom) == (1, 1, 1, 1):
            return None
        if right - left < 5 or bottom - top < 5:
            return None
        return left, top, right, bottom

    @staticmethod
    def _read_strategy_stage_rect(device, rect: tuple[int, int, int, int]) -> tuple[str, int]:
        """OCR stage text from Rect(x, y, w, h) using the validated AI-label pipeline."""
        x, y, width, height = (int(value) for value in rect)
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            return "", -1

        screenshot = device.screenshot().convert("RGB")
        image_width, image_height = screenshot.size
        x = min(x, image_width - 1)
        y = min(y, image_height - 1)
        right = min(x + width, image_width)
        bottom = min(y + height, image_height)
        if right <= x or bottom <= y:
            return "", -1

        crop = np.asarray(screenshot.crop((x, y, right, bottom)))
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        scaled = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        try:
            raw_text = pytesseract.image_to_string(
                scaled,
                lang="eng",
                config="--oem 3 --psm 8 -c tessedit_char_whitelist=AIai0123456789",
            ).strip()
        except pytesseract.TesseractError:
            return "", -1

        compact = re.sub(r"\\s+", "", raw_text).lower()
        match = re.fullmatch(r"ai(\\d{1,3})", compact)
        if not match:
            # Permit a digit-only result if OCR omits the "Ai" prefix entirely.
            match = re.fullmatch(r"(\\d{1,3})", compact)
        if match:
            candidate = int(match.group(1))
            if 1 <= candidate <= 100:
                return raw_text, candidate
        return raw_text, -1

    def _detect_strategy_status(
        self, device, elements, log_result=True, last_known_stage=-1
    ):
        """Detect Mưu Binh state from stage OCR and three independent text OCRs."""
        # OCR 1: current stage. Keep the caller's last known stage if this read fails.
        raw_stage = ""
        stage = -1
        stage_bounds = self._strategy_rect(elements, "ai_hien_tai")
        if stage_bounds is not None:
            left, top, right, bottom = stage_bounds
            raw_stage, stage = self._read_strategy_stage_rect(
                device, (left, top, right - left, bottom - top)
            )
        remembered_stage = stage if stage > 0 else last_known_stage

        # OCR 2: one region can contain either "bat_dau" or "tro_ve".
        # OCR 3: "hoi_thanh".
        # OCR 4: "nhan_thuong".
        def read_text_region(name):
            rect = self._strategy_rect(elements, name)
            if rect is None:
                return ""
            try:
                return self._screen_text_in_rect(device, rect)
            except Exception as exc:
                if log_result:
                    self.log_message.emit(f"OCR {name} thất bại: {exc}")
                return ""

        raw_start_return = read_text_region("bat_dau_tro_ve")
        raw_hall = read_text_region("hoi_thanh")
        raw_reward = read_text_region("nhan_thuong")
        start_return = self._normalize_ocr_match_text(raw_start_return)
        hall = self._normalize_ocr_match_text(raw_hall)
        reward = self._normalize_ocr_match_text(raw_reward)

        has_start = "batdau" in start_return
        has_return = "trove" in start_return
        has_hall = "hoithanh" in hall
        has_reward = "nhanthuong" in reward

        if has_reward:
            status = "cho_nhan_thuong"
        elif has_return:
            status = "dang_chien_dau"
        elif has_start and has_hall:
            status = "cho_chien_dau"
        elif stage <= 0 and not has_start and not has_return and not has_hall and not has_reward:
            status = (
                "hoan_thanh_muu_binh"
                if remembered_stage == 100
                else "that_bai_muu_binh"
            )
        else:
            status = "khong_xac_dinh"

        if log_result:
            if stage > 0:
                self.log_message.emit(
                    f"Đã phát hiện ải hiện tại: {stage}/100 (OCR: {raw_stage or '(trống)'})."
                )
            else:
                self.log_message.emit(
                    f"Không nhận diện được ải ở lần OCR này; ải đang lưu: "
                    f"{remembered_stage if remembered_stage > 0 else 'chưa có'} "
                    f"(OCR: {raw_stage or '(trống)'})."
                )
            self.log_message.emit(
                "OCR trạng thái Mưu Binh: "
                f"bat_dau/tro_ve='{raw_start_return or '(trống)'}', "
                f"hoi_thanh='{raw_hall or '(trống)'}', "
                f"nhan_thuong='{raw_reward or '(trống)'}'; kết quả={status}."
            )
        return status, stage

    def _run_strategy_reward(self, device, elements=None):
        """Claim one random Mưu Binh reward using its configured click point."""
        import random

        if elements is None:
            _regions_path, elements = self._strategy_regions()
        candidates = [
            (name, self._strategy_point(elements, name))
            for name in ("phan_thuong_1", "phan_thuong_2", "phan_thuong_3")
        ]
        candidates = [(name, point) for name, point in candidates if point is not None]
        if not candidates:
            self.log_message.emit(
                "Nhận thưởng Mưu Binh thất bại: các tọa độ phan_thuong_1/2/3 "
                "chưa được cập nhật khỏi placeholder (1, 1)."
            )
            return False
        name, (x, y) = random.choice(candidates)
        try:
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi nhận thưởng Mưu Binh.")
                return False
            device.shell(f"input tap {x} {y}")
            self.log_message.emit(
                f"Nhận thưởng Mưu Binh: chọn ngẫu nhiên {name}, click ({x}, {y})."
            )
            time.sleep(1)
            return True
        except Exception as exc:
            self.log_message.emit(f"Nhận thưởng Mưu Binh thất bại: {exc}")
            return False

    def _run_strategy_vuot_ai(self, device):
        """Run the Vượt Ải state loop; reward handling must be explicitly selected."""
        import time as _time

        _regions_path, elements = self._strategy_regions()
        button = self._strategy_point(elements, "button_vuot_ai")
        if button is None:
            self.log_message.emit(
                "Vượt Ải thất bại: tọa độ button_vuot_ai chưa được cập nhật khỏi placeholder."
            )
            return False
        consecutive_failures = 0
        battle_started = None
        reward_clicked = False
        current_stage = -1

        try:
            while True:
                if not self._wait_if_paused():
                    self.log_message.emit("Vượt Ải đã dừng theo yêu cầu.")
                    return False

                self.log_message.emit(
                    f"Vượt Ải: click nút Vượt Ải tại ({button[0]}, {button[1]})."
                )
                device.shell(f"input tap {button[0]} {button[1]}")
                consecutive_failures = consecutive_failures
                battle_started = None
                reward_clicked = False

                while True:
                    if not self._wait_if_paused():
                        self.log_message.emit("Vượt Ải đã dừng theo yêu cầu.")
                        return False
                    try:
                        status, stage = self._detect_strategy_status(
                            device, elements, log_result=False,
                            last_known_stage=current_stage,
                        )
                    except Exception as exc:
                        self.log_message.emit(f"Vượt Ải thất bại khi phát hiện trạng thái: {exc}")
                        return False

                    if stage > 0:
                        # After claiming a reward, do not roll back the stage
                        # counter if the UI briefly still shows the previous stage.
                        if not (reward_clicked and stage < current_stage):
                            current_stage = stage
                    if status == "hoan_thanh_muu_binh":
                        self.log_message.emit(
                            f"Mưu Binh hoàn thành: ải đang lưu là {current_stage}/100 "
                            "và cả 4 OCR đều không nhận diện được."
                        )
                        return True
                    if status == "that_bai_muu_binh":
                        self.log_message.emit(
                            f"Vượt Ải thất bại: cả 4 OCR đều không nhận diện được "
                            f"nhưng ải đang lưu là {current_stage if current_stage > 0 else 'không xác định'}, "
                            "khác 100."
                        )
                        return False
                    if status == "dang_chien_dau":
                        if battle_started is None:
                            battle_started = _time.monotonic()
                        if current_stage > 0:
                            self.log_message.emit(f"Đang vượt ải {current_stage}/100")
                        else:
                            self.log_message.emit(
                                "Đang chiến đấu — chưa xác định được ải hiện tại"
                            )
                        consecutive_failures = 0
                        if _time.monotonic() - battle_started >= 180:
                            self.log_message.emit(
                                "Vượt Ải thất bại: chiến đấu quá 3 phút; yêu cầu thoát Mưu Binh."
                            )
                            self._try_close_strategy(device, elements)
                            return False
                        if not self._strategy_wait(15):
                            self.log_message.emit("Vượt Ải đã dừng theo yêu cầu.")
                            return False
                        continue

                    if status == "cho_nhan_thuong":
                        if not self._config.get("task_receive_strategy_reward"):
                            self.log_message.emit(
                                "Vượt Ải thất bại: trạng thái cho_nhan_thuong nhưng "
                                "chưa tích chọn 'Nhận thưởng Mưu Binh' trong tab Tác Vụ. "
                                "Dừng xử lý Vượt Ải."
                            )
                            return False
                        if reward_clicked:
                            self.log_message.emit(
                                "Vượt Ải thất bại: đã gọi nhận thưởng nhưng trạng thái "
                                "cho_nhan_thuong vẫn còn; dừng để tránh click lặp."
                            )
                            return False
                        if not self._run_strategy_reward(device, elements):
                            self.log_message.emit(
                                "Vượt Ải thất bại do chức năng Nhận thưởng Mưu Binh thất bại; "
                                "dừng xử lý."
                            )
                            return False
                        reward_clicked = True
                        if current_stage > 0:
                            current_stage = min(current_stage + 1, 100)
                            self.log_message.emit(
                                f"Đã nhận thưởng thành công; cập nhật ải kế tiếp: "
                                f"{current_stage}/100."
                            )
                        else:
                            self.log_message.emit(
                                "Đã nhận thưởng nhưng chưa có số ải để tăng biến theo dõi."
                            )
                        if not self._strategy_wait(2):
                            return False
                        continue

                    if status in ("chuan_bi", "cho_chien_dau"):
                        if battle_started is not None or reward_clicked:
                            consecutive_failures += 1
                        else:
                            consecutive_failures += 1
                        if consecutive_failures >= 3:
                            self.log_message.emit(
                                "Vượt Ải thất bại 3 lần liên tiếp; yêu cầu thoát Mưu Binh."
                            )
                            self._try_close_strategy(device, elements)
                            return False
                        self.log_message.emit(
                            f"Vượt Ải chưa thành công (lần thất bại liên tiếp "
                            f"{consecutive_failures}/3); sẽ thử lại."
                        )
                        break

                    self.log_message.emit(
                        "Vượt Ải dừng an toàn: không xác định được trạng thái Mưu Binh; "
                        "không tự suy đoán thắng/thua."
                    )
                    return False
        except Exception as exc:
            self.log_message.emit(f"Vượt Ải gặp lỗi: {exc}")
            return False

    def _strategy_wait(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not self._wait_if_paused():
                return False
            time.sleep(min(0.25, max(0.01, deadline - time.monotonic())))
        return True

    def _try_close_strategy(self, device, elements):
        point = self._strategy_point(elements, "close_muu_binh")
        if point is None:
            self.log_message.emit(
                "Không thể tự thoát Mưu Binh: close_muu_binh vẫn là placeholder."
            )
            return False
        try:
            device.shell(f"input tap {point[0]} {point[1]}")
            self.log_message.emit(
                f"Đã click thoát màn hình Mưu Binh tại ({point[0]}, {point[1]})."
            )
            return True
        except Exception as exc:
            self.log_message.emit(f"Không thể thoát màn hình Mưu Binh: {exc}")
            return False

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
