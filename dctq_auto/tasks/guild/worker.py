"""Worker handlers for Quân đoàn tasks."""

import time
from types import SimpleNamespace


class GuildWorkerMixin:
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
            "task_donate_rations": "Đóng góp lương thảo",
            "task_donate_knb": "Đóng góp KNB",
        }
        label = task_labels[task_key]
        self._emit_task_progress(label, "running", 0, 1)
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

            elif task_key == "task_donate_knb":
                self.log_message.emit(
                    "Đóng góp KNB — click target dong_gop_knb từ regions.json."
                )
                x, y = ocr_client.tap_ocr_target("dong_gop_knb")
                time.sleep(0.8)
                self.log_message.emit(
                    f"Đã click dong_gop_knb tại ({x}, {y}); chưa tự xác nhận hoặc "
                    "thực hiện thêm thao tác trong hộp thoại."
                )

            elif task_key == "task_donate_rations":
                raise RuntimeError(
                    "Chưa triển khai thao tác đóng góp lương thảo: cần xác nhận "
                    "target trong regions.json và luồng xác nhận trước khi click."
                )

            self._emit_task_progress(label, "done", 1, 1)
            self.log_message.emit(
                f"Hoàn tất tác vụ '{label}'. Màn hình Quân đoàn vẫn được giữ nguyên."
            )
            return True
        except Exception as exc:
            self.log_message.emit(f"{label} thất bại: {exc}")
            self._emit_task_progress(label, "failed", 0, 1)
            return False
