"""Bước Clone Optimize: Điểm danh."""


def chay(worker, device, ocr_client) -> bool:
    """Gọi lại luồng điểm danh hằng ngày hiện có."""
    return bool(worker._run_daily_checkin(device, ocr_client))
