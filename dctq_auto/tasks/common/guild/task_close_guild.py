"""Đóng màn hình Quân đoàn và thoát chat nếu điều kiện OCR phù hợp."""

import time


def run(worker, account, device, ocr_client, log) -> bool:
    """Đóng cửa sổ Quân đoàn; nếu trở về màn hình chat thì thoát chat."""
    try:
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi thoát màn hình Quân đoàn.")
            return False

        regions_path = __import__("pathlib").Path(__file__).resolve().parents[2] / "regions.json"
        log(f"[{account.username}] Thoát Quân đoàn: click close_quan_doan từ regions.json.")
        ocr_client.tap_ocr_target("close_quan_doan", regions_path=regions_path)
        time.sleep(5)

        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng trước khi kiểm tra trạng thái chat Quân đoàn.")
            return False

        screen_text = worker._normalize_screen_text(worker._screen_text(device))
        if "vao quan doan" in screen_text:
            log(f"[{account.username}] OCR phát hiện 'vao_quan_doan'; thoát chat Quân đoàn.")
            ocr_client.tap_ocr_target("thoat_chat_quan_doan", regions_path=regions_path)
            time.sleep(0.8)
        else:
            log(
                f"[{account.username}] OCR không phát hiện 'vao_quan_doan'; "
                "không click thoat_chat_quan_doan."
            )
        log(f"[{account.username}] Đã xử lý flow thoát Quân đoàn.")
        return True
    except Exception as exc:
        log(f"[{account.username}] Thoát màn hình Quân đoàn thất bại: {exc}")
        return False
