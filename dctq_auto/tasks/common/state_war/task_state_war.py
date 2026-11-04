"""Điều phối chiến thuật Quốc chiến theo step được chọn."""

from pathlib import Path

from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUOC_CHIEN
from dctq_auto.tasks.common.state_war.task_run_state_war import (
    run_battle_strategy,
)


def pre_state_war(steps, strategy_path: str, log) -> bool:
    """Kiểm tra step Quốc chiến và chiến thuật JSON trước khi chạy."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN not in steps:
        log("Quốc chiến: không có step Quốc chiến trong danh sách; bỏ qua.")
        return False

    if not strategy_path or not str(strategy_path).strip():
        log("Quốc chiến: chưa chọn chiến thuật (strategy_path); bỏ qua.")
        return False

    log("Quốc chiến: tìm thấy step Quốc chiến và đã chọn chiến thuật; sẵn sàng.")
    return True


def post_state_war(steps, log) -> None:
    """Gỡ step Quốc chiến khỏi danh sách sau khi hoàn tất quy trình."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN in steps:
        steps.remove(_STEP_CHIEN_TRANH_QUOC_CHIEN)
        log("Quốc chiến: đã gỡ step Quốc chiến khỏi danh sách steps.")


def run_state_war(worker, account, steps, device, strategy_path: str, log) -> bool:
    """Chạy chiến thuật và luôn dọn step Quốc chiến sau khi bắt đầu."""
    if not pre_state_war(steps, strategy_path, log):
        return False

    log(f"[{account.username}] Bắt đầu quy trình Quốc chiến.")
    worker.task_progress_changed.emit(
        "Triển khai chiến thuật Quốc chiến", "running", 0, 1
    )
    success = False
    try:
        success = bool(
            run_battle_strategy(worker, device, Path(strategy_path))
        )
        return success
    except Exception as exc:
        log(f"[{account.username}] Quy trình Quốc chiến phát sinh lỗi: {exc}")
        worker.task_progress_changed.emit(
            "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
        )
        return False
    finally:
        post_state_war(steps, log)
