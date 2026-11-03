"""Orchestrate opening and the Mưu Binh auto-deploy/reward loop."""

from dctq_auto.config.constants import _STEP_STAGE_DEFENSE
from dctq_auto.tasks.common.stage_defense import (
    task_open_stage_defense,
    task_run_stage_defense,
)


def run(worker, account, device, log) -> bool:
    """Open Mưu Binh, then run until timeout or return to the main screen."""
    log(f"[{account.username}] Bắt đầu quy trình Mưu Binh.")
    try:
        opened = task_open_stage_defense.run(worker, account, device, log)
        if not opened:
            log(f"[{account.username}] Không mở được Mưu Binh; dừng tác vụ.")
            return False
        return task_run_stage_defense.run(worker, account, device, log)
    except Exception as exc:
        log(f"[{account.username}] Quy trình Mưu Binh phát sinh lỗi: {exc}")
        return False


def pre_stage_defense(steps, log) -> bool:
    """Kiểm tra danh sách steps có yêu cầu chạy Mưu Binh hay không."""
    if _STEP_STAGE_DEFENSE not in steps:
        log("Mưu Binh: không có step_stage_defense trong danh sách; bỏ qua.")
        return False

    log("Mưu Binh: tìm thấy step_stage_defense; sẵn sàng thực hiện.")
    return True
