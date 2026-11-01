"""Điều phối các tác vụ thuộc [Shop Chiến Tranh]."""

from dctq_auto.tasks.common.shop.war import (
    task_buy_fortune_lot,
    task_close_shop_war,
    task_open_shop_war,
)


_WAR_SHOP_TASKS = (
    (task_buy_fortune_lot, "Mua Quẻ Lành"),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Shop Chiến Tranh, lần lượt chạy danh sách task con, rồi đóng tab."""
    if not task_open_shop_war.run(
        worker, account, steps, device, ocr_client, log, screenshot=screenshot
    ):
        log(f"[{account.username}] Không mở được [Shop Chiến Tranh]; bỏ qua các task con.")
        return steps

    try:
        for task, task_name in _WAR_SHOP_TASKS:
            try:
                steps = task.run(
                    worker, account, steps, device, ocr_client, log, screenshot=None
                )
            except Exception as exc:
                log(f"[{account.username}] {task_name} thất bại: {exc}")
        return steps
    finally:
        try:
            if not task_close_shop_war.run(
                worker, account, device, ocr_client, log
            ):
                log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát [Shop Chiến Tranh].")
        except Exception as exc:
            log(f"[{account.username}] Lỗi khi đóng [Shop Chiến Tranh]: {exc}")
