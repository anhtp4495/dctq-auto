"""Điều phối chiến thuật Quốc chiến theo step được chọn."""

from pathlib import Path

from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUOC_CHIEN
from dctq_auto.tasks.common.state_war.task_run_state_war import (
    get_battle_step_progress_label,
    load_battle_strategy,
    run_battle_strategy,
)


def pre_state_war(
    steps,
    strategy_path: str,
    log,
    add_progress_item=None,
) -> bool:
    """Kiểm tra chiến thuật và tạo danh sách tiến trình Quốc chiến."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN not in steps:
        log("Quốc chiến: không có step Quốc chiến trong danh sách; bỏ qua.")
        return False

    if not strategy_path or not str(strategy_path).strip():
        log("Quốc chiến: chưa chọn chiến thuật (strategy_path); bỏ qua.")
        return False

    try:
        _data, strategy_steps = load_battle_strategy(strategy_path)
    except (OSError, ValueError) as exc:
        log(f"Quốc chiến: chiến thuật không hợp lệ: {exc}")
        return False

    if add_progress_item is not None:
        add_progress_item("Bắt đầu", 1)
        for strategy_step in strategy_steps:
            add_progress_item(
                get_battle_step_progress_label(strategy_step),
                1,
            )
        add_progress_item("Kết thúc", 1)

    log("Quốc chiến: tìm thấy step Quốc chiến và đã chọn chiến thuật; sẵn sàng.")
    return True


def post_state_war(steps, log) -> None:
    """Gỡ step Quốc chiến khỏi danh sách sau khi hoàn tất quy trình."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN in steps:
        steps.remove(_STEP_CHIEN_TRANH_QUOC_CHIEN)
        log("Quốc chiến: đã gỡ step Quốc chiến khỏi danh sách steps.")


def run_state_war(worker, account, steps, device, strategy_path: str, log) -> bool:
    """Chạy chiến thuật và luôn dọn step Quốc chiến sau khi bắt đầu."""
    if not pre_state_war(
        steps,
        strategy_path,
        log,
        add_progress_item=worker.task_progress_item_added.emit,
    ):
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
