"""Thao tác dùng chung để mở màn hình Hoạt động."""


def run(self, account, device, ocr_client, log) -> bool:
    """Mở màn hình Hoạt động và xác nhận kết quả bằng logic đã có."""
    log(f"[{account.username}] Bắt đầu mở màn hình Hoạt động.")

    open_activity = getattr(self, "_run_open_activity", None)
    if not callable(open_activity):
        log(
            f"[{account.username}] Không tìm thấy hàm _run_open_activity "
            "để mở màn hình Hoạt động."
        )
        return False

    try:
        result = bool(open_activity(device))
    except Exception as exc:
        log(f"[{account.username}] Mở màn hình Hoạt động thất bại: {exc}")
        return False

    if result:
        log(f"[{account.username}] Đã mở/xác nhận màn hình Hoạt động.")
    else:
        log(f"[{account.username}] Không mở/xác nhận được màn hình Hoạt động.")
    return result
