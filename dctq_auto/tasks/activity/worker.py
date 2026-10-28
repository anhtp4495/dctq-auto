"""Worker handlers for Hoạt Động and Phúc Lợi tasks."""

import json
import time
from pathlib import Path

import cv2
import numpy as np

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


class ActivityWorkerMixin:
    def _activity_phuc_loi_visible(self, device, screenshot=None) -> tuple[bool, str]:
        """Return whether OCR can identify the Hoạt động > Phúc lợi screen."""
        if screenshot is None:
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

    def run_open_activity(self, device, screenshot=None) -> bool:
        """Mở Hoạt động bằng Template Matching, theo cùng pattern handle_post_login."""
        template_names = (
            "hoat_dong/dang_chon_man_hinh_hoat_dong",
            "hoat_dong/chua_chon_man_hinh_hoat_dong",
        )
        templates = get_templates(template_names)

        try:
            if not self._wait_if_paused():
                return False
            if screenshot is None:
                screenshot = device.screenshot()
            screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
        except Exception as exc:
            self.log_message.emit(f"Không chụp được màn hình để nhận diện Hoạt động: {exc}")
            return False

        for template_name in template_names:
            template = templates.get(template_name)
            if template is None:
                self.log_message.emit(f"Không tải được template {template_name}; bỏ qua.")
                continue

            try:
                match = match_template(
                    screen_bgr,
                    template.image,
                    threshold=template.threshold,
                    method=template.method,
                )
            except (ValueError, cv2.error) as exc:
                self.log_message.emit(
                    f"Lỗi template matching {template_name}: {exc}"
                )
                continue

            if match is None:
                continue

            report_template_match(
                self.log_message.emit,
                context="Hoạt động",
                template=template,
                match=match,
            )

            if template.id == "dang_chon_man_hinh_hoat_dong":
                self.log_message.emit("Template xác nhận đã ở màn hình Hoạt động.")
                return True

            if template.id == "chua_chon_man_hinh_hoat_dong":
                screen_width, screen_height = screenshot.size
                x = round(0.035937 * screen_width)
                y = round(0.732407 * screen_height)
                self.log_message.emit(
                    f"Template xác nhận chưa chọn màn hình Hoạt động; click ({x}, {y})."
                )
                try:
                    if not self._wait_if_paused():
                        return False
                    device.shell(f"input tap {x} {y}")
                    time.sleep(3.0)
                    if not self._wait_if_paused():
                        return False
                    return self.run_open_activity(device, screenshot=device.screenshot())
                except Exception as exc:
                    self.log_message.emit(f"Mở màn hình Hoạt động thất bại: {exc}")
                    return False

        self.log_message.emit(
            "Không khớp template dang_chon_man_hinh_hoat_dong hoặc "
            "chua_chon_man_hinh_hoat_dong; không thực hiện click."
        )
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
            if not self.run_open_activity(device):
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
                    round(145 / 1080 * screen_height),
                    max(1, round(384 / 1920 * screen_width)),
                    max(1, round(269 / 1080 * screen_height)),
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

            screenshot = device.screenshot()
            screen_width, screen_height = screenshot.size
            # Đọc RECT đã lưu trong regions.json (tọa độ gốc 1920x1080).
            regions_path = Path(__file__).resolve().parents[1] / "common" / "regions.json"
            with regions_path.open("r", encoding="utf-8") as stream:
                regions_data = json.load(stream)
            feature_region = next(
                element
                for element in regions_data["regions"]["hoat_dong"]["elements"]
                if element["name"] == "ocr_cac_tinh_nang_hoat_dong"
            )
            saved_rect = feature_region["rect"]
            selected_rect = (
                round(saved_rect["x"] / 1920 * screen_width),
                round(saved_rect["y"] / 1080 * screen_height),
                round(saved_rect["width"] / 1920 * screen_width),
                round(saved_rect["height"] / 1080 * screen_height),
            )
            # _ocr_words_in_rect expects (left, top, right, bottom), while
            # regions.json stores RECT as (x, y, width, height).
            ocr_rect = (
                selected_rect[0],
                selected_rect[1],
                selected_rect[0] + selected_rect[2],
                selected_rect[1] + selected_rect[3],
            )
            self.log_message.emit(
                "Lễ bao Quốc vận — BƯỚC 3: Tìm text le_bao_quoc bằng OCR "
                f"Rect ({ocr_rect[0]}; {ocr_rect[1]}; {ocr_rect[2]}; {ocr_rect[3]}) "
                "steps: [gray, white_text] psm [11]."
            )
            # OCR đôi khi đọc chữ "quốc" thành "quec" (như log phân tích OCR),
            # nên chấp nhận biến thể này để không bỏ sót đúng mục Lễ bao Quốc vận.
            gift_match = self._tap_ocr_phrase_in_rect(
                device, ("le bao quoc", "le bao quec"), ocr_rect,
                steps=("gray", "white_text"), psm=(11,), tap=False,
            )
            if gift_match is None:
                # Lễ bao Quốc vận nằm gần đầu danh sách; vuốt từ A xuống B
                # để đưa các mục phía trên vào vùng nhìn thấy rồi OCR lại.
                swipe_ax = round(347 / 1920 * screen_width)
                swipe_ay = round(349 / 1080 * screen_height)
                swipe_bx = round(362 / 1920 * screen_width)
                swipe_by = round(747 / 1080 * screen_height)
                self.log_message.emit(
                    "Không tìm thấy le_bao_quoc; vuốt danh sách từ A -> B "
                    f"({swipe_ax}, {swipe_ay}) -> ({swipe_bx}, {swipe_by}) rồi OCR lại."
                )
                device.shell(
                    f"input swipe {swipe_ax} {swipe_ay} {swipe_bx} {swipe_by} 400"
                )
                time.sleep(0.6)
                if not self._wait_if_paused():
                    return False
                gift_match = self._tap_ocr_phrase_in_rect(
                    device, ("le bao quoc", "le bao quec"), ocr_rect,
                    steps=("gray", "white_text"), psm=(11,), tap=False,
                )
            if gift_match is None:
                self.log_message.emit(
                    "Không tìm thấy mục Lễ bao Quốc vận bằng OCR sau khi vuốt; bỏ qua tác vụ này."
                )
                return False
            gift_x, gift_y, _ = gift_match
            device.shell(f"input tap {gift_x} {gift_y}")

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
            diem_danh_match = self._tap_ocr_phrase_in_rect(
                device, ("diem danh",), diem_danh_rect, tap=False
            )
            if diem_danh_match is None:
                # Điểm danh nằm phía dưới danh sách; vuốt từ B lên A rồi OCR lại.
                swipe_ax = round(347 / 1920 * screen_width)
                swipe_ay = round(349 / 1080 * screen_height)
                swipe_bx = round(362 / 1920 * screen_width)
                swipe_by = round(747 / 1080 * screen_height)
                self.log_message.emit(
                    "Không tìm thấy diem_danh; vuốt danh sách từ B -> A "
                    f"({swipe_bx}, {swipe_by}) -> ({swipe_ax}, {swipe_ay}) rồi OCR lại."
                )
                device.shell(
                    f"input swipe {swipe_bx} {swipe_by} {swipe_ax} {swipe_ay} 400"
                )
                time.sleep(0.6)
                if not self._wait_if_paused():
                    self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                    return False
                diem_danh_match = self._tap_ocr_phrase_in_rect(
                    device, ("diem danh",), diem_danh_rect, tap=False
                )
            if diem_danh_match is None:
                raise RuntimeError(
                    "OCR không tìm thấy nút Điểm danh trong RECT đã cấu hình "
                    "kể cả sau khi vuốt B -> A; dừng, không click fallback."
                )
            diem_danh_x, diem_danh_y, _ = diem_danh_match
            device.shell(f"input tap {diem_danh_x} {diem_danh_y}")
            time.sleep(5.0)

            if not self._wait_if_paused():
                self.log_message.emit("Điểm danh đã dừng theo yêu cầu.")
                return False

            self.log_message.emit("BƯỚC 4/5: Click 31 ô theo thứ tự ngày 31 → ngày 1.")
            calendar_image = device.screenshot()
            calendar_width, calendar_height = calendar_image.size
            grid_left = (484 / 1920) * calendar_width
            grid_top = (402 / 1080) * calendar_height
            grid_width = ((1822 - 484) / 1920) * calendar_width
            grid_height = ((998 - 402) / 1080) * calendar_height

            cells_reverse = tuple(range(31, 0, -1))
            row_ranges = ((1, 9), (10, 18), (19, 27), (28, 31))
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
            self.log_message.emit("Đã hoàn tất flow Điểm danh: click đủ 31 ô từ ngày 31 đến ngày 1.")
            return True
        except Exception as exc:
            self.log_message.emit(f"Điểm danh thất bại, dừng ngay (không retry): {exc}")
            return False
