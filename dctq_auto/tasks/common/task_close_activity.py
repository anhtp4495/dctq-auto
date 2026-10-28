"""Thao tác dùng chung để đóng màn hình Hoạt động / Phúc Lợi."""


def task_close_activity(self, account, device, ocr_client, log) -> bool:
    """Đóng màn hình Hoạt động bằng logic đóng màn hình hiện có."""
    log(f"[{account.username}] Bắt đầu đóng màn hình Hoạt động / Phúc Lợi.")

    close_activity = getattr(self, "_run_close_activity", None)
    if not callable(close_activity):
        log(
            f"[{account.username}] Không tìm thấy hàm _run_close_activity "
            "để đóng màn hình Hoạt động / Phúc Lợi."
        )
        return False

    try:
        result = bool(close_activity(device))
    except Exception as exc:
        log(f"[{account.username}] Đóng màn hình Hoạt động / Phúc Lợi thất bại: {exc}")
        return False

    if result:
        log(f"[{account.username}] Đã đóng màn hình Hoạt động / Phúc Lợi.")
    else:
        log(f"[{account.username}] Không đóng được màn hình Hoạt động / Phúc Lợi.")
    return result
