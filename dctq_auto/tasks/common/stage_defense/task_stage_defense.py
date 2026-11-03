"""Orchestrate opening, stage polling, and closing for Mưu Binh."""

from dctq_auto.tasks.common.stage_defense import (
    task_close_stage_defense,
    task_open_stage_defense,
    task_run_stage_defense,
)


def run(worker, account, device, log) -> bool:
    """Run Mưu Binh and verify the close flow after the stage loop."""
    log(f"[{account.username}] Bắt đầu quy trình Mưu Binh.")
    opened = False
    run_ok = False
    close_ok = False
    try:
        opened = task_open_stage_defense.run(worker, account, device, log)
        if not opened:
            log(f"[{account.username}] Không mở được Mưu Binh; bỏ qua theo dõi trận.")
        else:
            run_ok = task_run_stage_defense.run(worker, account, device, log)
    except Exception as exc:
        log(f"[{account.username}] Quy trình Mưu Binh phát sinh lỗi: {exc}")
    finally:
        if opened:
            try:
                close_ok = task_close_stage_defense.run(worker, account, device, log)
                log(
                    f"[{account.username}] Tác vụ đóng Mưu Binh "
                    f"{'thành công' if close_ok else 'chưa xác nhận được'}."
                )
            except Exception as exc:
                log(f"[{account.username}] Đóng Mưu Binh phát sinh lỗi: {exc}")
    return run_ok and close_ok
