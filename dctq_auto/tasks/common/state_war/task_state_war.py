"""Điều phối chiến thuật Quốc chiến theo step được chọn."""

from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUOC_CHIEN
from dctq_auto.tasks.common.battle.battle_strategies.custom_battle import (
    CustomBattle,
    load_strategy,
)


def pre_state_war(
    steps,
    strategy_path: str,
    log,
    add_progress_item=None,
) -> bool:
    """Kiểm tra step Quốc chiến và xác thực chiến thuật JSON."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN not in steps:
        log("Quốc chiến: không có step Quốc chiến trong danh sách; bỏ qua.")
        return False

    if not strategy_path or not str(strategy_path).strip():
        log("Quốc chiến: chưa chọn chiến thuật (strategy_path); bỏ qua.")
        return False

    try:
        load_strategy(strategy_path)
    except (OSError, ValueError) as exc:
        log(f"Quốc chiến: chiến thuật không hợp lệ: {exc}")
        return False

    log("Quốc chiến: tìm thấy step Quốc chiến và đã chọn chiến thuật; sẵn sàng.")
    return True


def post_state_war(steps, log) -> None:
    """Gỡ step Quốc chiến khỏi danh sách sau khi hoàn tất quy trình."""
    if _STEP_CHIEN_TRANH_QUOC_CHIEN in steps:
        steps.remove(_STEP_CHIEN_TRANH_QUOC_CHIEN)
        log("Quốc chiến: đã gỡ step Quốc chiến khỏi danh sách steps.")


def run_state_war(worker, account, steps, device, strategy_path: str, log) -> bool:
    """Chạy chiến thuật Quốc chiến bằng bộ thực thi JSON dùng chung."""
    if not pre_state_war(steps, strategy_path, log):
        return False

    log(f"[{account.display_name}] Bắt đầu quy trình Quốc chiến.")
    worker._emit_task_progress(
        "Triển khai chiến thuật Quốc chiến", "running", 0, 1
    )
    try:
        context = {
            "worker": worker,
            "account": account,
            "device": device,
            "log": log,
            "battle_strategy_path": strategy_path,
        }
        success = bool(CustomBattle().deploy(context))
        if success:
            worker._emit_task_progress(
                "Triển khai chiến thuật Quốc chiến", "done", 1, 1
            )
        else:
            worker._emit_task_progress(
                "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
            )
        return success
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình Quốc chiến phát sinh lỗi: {exc}")
        worker._emit_task_progress(
            "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
        )
        return False
    finally:
        post_state_war(steps, log)
