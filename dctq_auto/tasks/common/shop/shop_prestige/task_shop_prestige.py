"""Điều phối các tác vụ thuộc [Shop Danh Vọng]."""

from dctq_auto.tasks.common.shop.shop_prestige import task_buy_fortune_lot


_PRESTIGE_SHOP_TASKS = (
    (task_buy_fortune_lot, "Mua Quẻ Lành"),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Lần lượt gọi các task con thuộc Shop Danh Vọng."""
    for task, task_name in _PRESTIGE_SHOP_TASKS:
        try:
            steps = task.run(
                worker, account, steps, device, ocr_client, log, screenshot=screenshot
            )
        except Exception as exc:
            log(f"[{account.username}] {task_name} thất bại: {exc}")
    return steps
