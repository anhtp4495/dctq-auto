"""Bước Clone Optimize: Quốc chiến."""

import time


def chay(worker, device, ocr_client) -> bool:
    """Mở Chiến tranh và xác nhận OCR thấy mục Quốc chiến."""
    ocr_client.tap_ocr_target("chien_tranh")
    time.sleep(1.5)
    screen_text = worker._normalize_screen_text(worker._screen_text(device))
    return "quoc chien" in screen_text or "quoc_chien" in screen_text
