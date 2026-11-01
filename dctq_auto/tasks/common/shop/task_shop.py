"""Điều phối các tác vụ thuộc màn hình [Cửa hàng]."""

from dctq_auto.tasks.common.shop import task_close_shop, task_open_shop
from dctq_auto.tasks.common.shop.shop_war import task_shop_war


_SHOP_TASKS = (
    (task_shop_war, "Shop Chiến Tranh"),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở shop, lần lượt chạy danh sách task con, sau đó đóng giao diện shop."""
    shop_opened = False
    try:
        if not task_open_shop.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được [Cửa hàng]; giữ nguyên step.")
            return steps
        shop_opened = True

        for task, task_name in _SHOP_TASKS:
            try:
                steps = task.run(
                    worker, account, steps, device, ocr_client, log, screenshot=None
                )
            except Exception as exc:
                log(f"[{account.username}] {task_name} thất bại: {exc}")

        return steps
    finally:
        if shop_opened:
            try:
                closed = task_close_shop.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được [Cửa hàng].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi đóng [Cửa hàng]: {exc}")
