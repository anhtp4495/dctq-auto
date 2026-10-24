"""Worker handlers for Quân đoàn tasks."""

import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytesseract


class GuildWorkerMixin:
    def _run_enter_guild(self, device, ocr_client) -> bool:
        """Open guild chat, click its entry button, then verify the guild screen."""
        try:
            if not self._wait_if_paused():
                return False

            import json

            regions_path = Path(__file__).resolve().parents[1] / "common" / "regions.json"
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

            # BƯỚC 3: xác nhận đã vào Quân đoàn bằng OCR nút Báo danh.
            # Thử tối đa 3 lần vì giao diện có thể tải chậm hoặc mạng yếu.
            from difflib import SequenceMatcher

            check_rect = (1527, 952, 1848, 999)
            expected_text = "bao_danh_quan_doan"
            matched = False
            last_text = ""
            last_ratio = 0.0

            for attempt in range(1, 4):
                if not self._wait_if_paused():
                    return False

                last_text, actual_rect, _ = color_text_ocr(check_rect, 38.0)
                normalized_text = self._normalize_ocr_match_text(last_text)
                normalized_expected = self._normalize_ocr_match_text(expected_text)
                last_ratio = (
                    SequenceMatcher(None, normalized_expected, normalized_text).ratio()
                    if normalized_text and normalized_expected else 0.0
                )

                self.log_message.emit(
                    f"Vào quân đoàn — BƯỚC 3: OCR nút bao_danh_quan_doan "
                    f"lần {attempt}/3 trong RECT {actual_rect}; "
                    f"text: {last_text or '(trống)'}; độ khớp: {last_ratio:.1%}."
                )

                if last_ratio > 0.25:
                    matched = True
                    break

                if attempt < 3:
                    time.sleep(1.0)

            if not matched:
                raise RuntimeError(
                    "Đã click 'Vào quân đoàn' nhưng sau 3 lần OCR, text trong "
                    f"RECT {check_rect} không khớp '{expected_text}' trên 25%. "
                    f"Text cuối: {last_text or '(trống)'}; độ khớp cuối: {last_ratio:.1%}."
                )

            self.log_message.emit(
                f"Đã xác nhận mở màn hình Quân đoàn thành công: OCR khớp "
                f"'{expected_text}' ở mức {last_ratio:.1%} (>25%)."
            )
            return True
        except Exception as exc:
            self.log_message.emit(f"Vào quân đoàn thất bại, dừng luồng: {exc}")
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
