"""Điều phối các tác vụ thuộc [Shop Chiến Tranh]."""

from dctq_auto.config.constants import _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH
from dctq_auto.tasks.common.shop.shop_war import task_open_shop_war
from dctq_auto.tasks.common.shop.shop_war.shop_prestige import task_shop_prestige


_WAR_SHOP_TASKS = (
    (task_shop_prestige, "Shop Danh Vọng"),
)

# Chỉ đăng ký những step Shop Chiến Tranh đã có task runner hoàn chỉnh.
_WAR_SHOP_STEP_IDS = {
    _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH,
}


def pre_shop_war(steps, log) -> bool:
    """Kiểm tra có step Shop Chiến Tranh đã triển khai nào được chọn không."""
    selected_steps = _WAR_SHOP_STEP_IDS.intersection(steps)
    if not selected_steps:
        log("Shop Chiến Tranh: không có step đã triển khai trong danh sách; bỏ qua.")
        return False

    log(
        "Shop Chiến Tranh: có step được chọn — "
        + ", ".join(sorted(selected_steps))
        + "."
    )
    return True


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Shop Chiến Tranh rồi lần lượt chạy danh sách shop con."""
    if not task_open_shop_war.run(
        worker, account, steps, device, ocr_client, log, screenshot=screenshot
    ):
        log(f"[{account.display_name}] Không mở được [Shop Chiến Tranh]; bỏ qua các shop con.")
        return steps

    for task, task_name in _WAR_SHOP_TASKS:
        try:
            steps = task.run(
                worker, account, steps, device, ocr_client, log, screenshot=None
            )
        except Exception as exc:
            log(f"[{account.display_name}] {task_name} thất bại: {exc}")

    return steps
