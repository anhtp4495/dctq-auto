"""Điều phối một lượt chạy chiến thuật Quốc chiến."""

from dctq_auto.tasks.common.tasks.state_war.task_run_state_war import (
    run_battle_strategy,
)


def run_state_war(worker, device, strategy_path: str) -> bool:
    """Chạy chiến thuật đã chọn; màn hình Quốc chiến cần được mở sẵn."""
    if not strategy_path:
        worker.log_message.emit("Quốc chiến: chưa chọn chiến thuật JSON.")
        worker.task_progress_changed.emit(
            "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
        )
        return False

    worker.task_progress_changed.emit(
        "Triển khai chiến thuật Quốc chiến", "running", 0, 1
    )
    try:
        return run_battle_strategy(worker, device, strategy_path)
    except Exception as exc:
        worker.log_message.emit(f"Quốc chiến thất bại: {exc}")
        worker.task_progress_changed.emit(
            "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
        )
        return False
