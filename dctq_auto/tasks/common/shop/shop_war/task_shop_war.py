"""Điều phối các tác vụ thuộc [Shop Chiến Tranh]."""

from dctq_auto.tasks.common.shop.shop_war import task_open_shop_war
from dctq_auto.tasks.common.shop.shop_war.shop_prestige import task_shop_prestige


_WAR_SHOP_TASKS = (
    (task_shop_prestige, "Shop Danh Vọng"),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Shop Chiến Tranh rồi lần lượt chạy danh sách shop con."""
    if not task_open_shop_war.run(
        worker, account, steps, device, ocr_client, log, screenshot=screenshot
    ):
        log(f"[{account.username}] Không mở được [Shop Chiến Tranh]; bỏ qua các shop con.")
        return steps

    for task, task_name in _WAR_SHOP_TASKS:
        try:
            steps = task.run(
                worker, account, steps, device, ocr_client, log, screenshot=None
            )
        except Exception as exc:
            log(f"[{account.username}] {task_name} thất bại: {exc}")

    return steps
