"""Điều phối chiến thuật Quốc chiến theo step được chọn."""

from pathlib import Path

from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUOC_CHIEN
from dctq_auto.tasks.common.state_war.task_run_state_war import (
    run_battle_strategy,
)


def pre_state_war(steps, strategy_path: str, log) -> bool:
    """Kiểm tra step Quốc chiến và chiến thuật JSON trước khi chạy."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN not in steps:
        log("Quốc chiến: không có chien_tranh_quoc_chien trong danh sách steps; bỏ qua.")
        return False

    if not strategy_path or not str(strategy_path).strip():
        log("Quốc chiến: chưa chọn chiến thuật (strategy_path); bỏ qua.")
        return False

    log("Quốc chiến: tìm thấy chien_tranh_quoc_chien và đã chọn chiến thuật; sẵn sàng.")
    return True


def run_state_war(worker, account, steps, device, strategy_path: str, log) -> bool:
    """Chạy chiến thuật đã chọn sau khi pre_state_war xác nhận hợp lệ."""
    if not pre_state_war(steps, strategy_path, log):
        return False

    log(f"[{account.username}] Bắt đầu quy trình Quốc chiến.")
    worker.task_progress_changed.emit(
        "Triển khai chiến thuật Quốc chiến", "running", 0, 1
    )
    try:
        return run_battle_strategy(worker, device, Path(strategy_path))
    except Exception as exc:
        log(f"[{account.username}] Quy trình Quốc chiến phát sinh lỗi: {exc}")
        worker.task_progress_changed.emit(
            "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
        )
        return False
