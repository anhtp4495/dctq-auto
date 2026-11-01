"""Điều phối các tác vụ thuộc [Shop Chiến Tranh]."""

from dctq_auto.config.constants import _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH
from dctq_auto.tasks.common.shop.shop_war import task_open_shop_war
from dctq_auto.tasks.common.shop.shop_war.shop_prestige import task_shop_prestige


_WAR_SHOP_TASKS = (
    (task_shop_prestige, "Shop Danh Vọng"),
)


# Chỉ đăng ký những step Shop Chiến Tranh đã có task runner hoàn chỉnh.\n_WAR_SHOP_STEP_IDS = {\n    _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH,\n}\n\n\ndef pre_shop_war(steps, log) -> bool:\n    """Kiểm tra có step Shop Chiến Tranh đã triển khai nào được chọn không."""\n    selected_steps = _WAR_SHOP_STEP_IDS.intersection(steps)\n    if not selected_steps:\n        log("Shop Chiến Tranh: không có step đã triển khai trong danh sách; bỏ qua.")\n        return False\n\n    log("Shop Chiến Tranh: có step được chọn — " + ", ".join(sorted(selected_steps)) + ".")\n    return True\n\n\ndef run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:\n    """Mở Shop Chiến Tranh rồi lần lượt chạy danh sách shop con."""
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
