"""Điều phối các tác vụ thuộc [Shop Danh Vọng]."""

from dctq_auto.tasks.common.shop.shop_war.shop_prestige import (
    task_buy_fortune_lot,
    task_open_shop_prestige,
)


_PRESTIGE_SHOP_TASKS = (
    (task_buy_fortune_lot, "Mua Quẻ Lành"),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Shop Danh Vọng rồi lần lượt gọi các task con."""
    if not task_open_shop_prestige.run(
        worker, account, steps, device, ocr_client, log, screenshot=screenshot
    ):
        log(f"[{account.display_name}] Không mở được [Shop Danh Vọng]; bỏ qua các tác vụ con.")
        return steps

    for task, task_name in _PRESTIGE_SHOP_TASKS:
        try:
            steps = task.run(
                worker, account, steps, device, ocr_client, log, screenshot=None
            )
        except Exception as exc:
            log(f"[{account.display_name}] {task_name} thất bại: {exc}")
    return steps
