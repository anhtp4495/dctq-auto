"""Thao tác dùng chung để mở màn hình Hoạt động."""


def run_open_activity(
    self, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở màn hình Hoạt động; có thể tái sử dụng screenshot đã chụp."""
    log(f"[{account.username}] Bắt đầu mở màn hình Hoạt động.")

    open_activity = getattr(self, "run_open_activity", None)
    if not callable(open_activity):
        log(
            f"[{account.username}] Không tìm thấy hàm run_open_activity "
            "để mở màn hình Hoạt động."
        )
        return False

    try:
        result = bool(open_activity(device, screenshot=screenshot))
    except Exception as exc:
        log(f"[{account.username}] Mở màn hình Hoạt động thất bại: {exc}")
        return False

    if result:
        log(f"[{account.username}] Đã mở/xác nhận màn hình Hoạt động.")
    else:
        log(f"[{account.username}] Không mở/xác nhận được màn hình Hoạt động.")
    return result


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới run_open_activity."""
    return run_open_activity(
        self, account, device, ocr_client, log, screenshot=screenshot
    )
