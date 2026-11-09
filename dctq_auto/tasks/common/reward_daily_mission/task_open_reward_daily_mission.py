"""Mở giao diện nhận thưởng nhiệm vụ hằng ngày."""

import time


_MAX_TRIES = 3
_POLL_INTERVAL = 1


def run(worker, account, device, ocr_client, log, current_try=1) -> bool:
    """Khung mở giao diện; bổ sung nhận diện và thao tác ở bước triển khai sau."""
    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu mở giao diện nhiệm vụ hằng ngày.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.display_name}] Chưa mở được giao diện nhiệm vụ hằng ngày "
            f"sau {_MAX_TRIES} lần thử."
        )
        return False

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang mở nhiệm vụ hằng ngày.")
        return False

    time.sleep(_POLL_INTERVAL)
    return run(
        worker,
        account,
        device,
        ocr_client,
        log,
        current_try=current_try + 1,
    )
