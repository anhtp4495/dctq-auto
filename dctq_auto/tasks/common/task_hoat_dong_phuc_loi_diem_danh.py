"""Tác vụ Clone Optimize: Điểm danh trong nhóm Hoạt động - Phúc lợi."""


def run(worker, device, ocr_client) -> bool:
    """Chạy luồng điểm danh hằng ngày hiện có."""
    return bool(worker._run_daily_checkin(device, ocr_client))
