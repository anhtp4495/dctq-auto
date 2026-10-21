"""Thao tác hậu cần quân đoàn, bao gồm Cầu vận."""

import time


def run_guild_logistics(worker, account, device, ocr_client) -> bool:
    """Chạy thao tác Cầu vận; trả về False nếu worker được yêu cầu dừng."""
    try:
        worker.log_message.emit(
            f"[{account.username}] Đang mở Cầu vận quân đoàn."
        )
        shop_text = worker._normalize_screen_text(worker._screen_text(device))
        if not any(marker in shop_text for marker in (
            "cua hang quan doan", "cau van quan doan", "tui phuc", "anh hung"
        )):
            worker.log_message.emit(
                f"[{account.username}] Chưa nhận diện cửa hàng quân đoàn trước khi mở Cầu vận; "
                f"thử kiểm tra OCR: {shop_text[:180]}"
            )
        ocr_client.tap_ocr_target("cau_van_quan_doan")
        time.sleep(1.5)
        fortune_text = ""
        fortune_screen_found = False
        for fortune_attempt in range(5):
            if not worker._wait_if_paused():
                worker.log_message.emit("Đã dừng theo yêu cầu.")
                return False
            fortune_text = worker._normalize_screen_text(worker._screen_text(device))
            fortune_markers = ("giai hien tai", "xepthang", "cau van")
            if any(marker in fortune_text for marker in fortune_markers):
                fortune_screen_found = True
                break
            if fortune_attempt < 4:
                time.sleep(1)
        if fortune_screen_found:
            worker.log_message.emit(
                f"[{account.username}] Đã xác nhận màn hình Cầu vận: {fortune_text[:220]}"
            )
            for draw_attempt in range(5):
                if not worker._wait_if_paused():
                    worker.log_message.emit("Đã dừng theo yêu cầu.")
                    return False
                ocr_client.tap_ocr_target("cau_van")
                time.sleep(0.8)
                worker.log_message.emit(
                    f"[{account.username}] Đã bấm Cầu vận lần {draw_attempt + 1}/5."
                )
            ocr_client.tap_ocr_target("close_cau_van")
            time.sleep(0.8)
            worker.log_message.emit(
                f"[{account.username}] Đã hoàn tất 5 lần bấm Cầu vận và đóng cửa sổ."
            )
        else:
            worker.log_message.emit(
                f"[{account.username}] Không xác nhận được màn hình Cầu vận; "
                f"không bấm 5 lần để tránh thao tác nhầm. OCR: {fortune_text[:220] or '(trống)'}"
            )
            return False
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Lỗi thao tác hậu cần quân đoàn: {exc}"
        )
        worker.task_progress_changed.emit(
            f"{account.username} - Hậu cần quân đoàn", "failed", 0, 1
        )
        return False
    return True
