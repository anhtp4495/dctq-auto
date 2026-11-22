"""Điều phối quy trình Trưởng Thành."""

from dctq_auto.tasks.common.maturity import (
    task_close_maturity,
    task_open_maturity,
    task_run_maturity,
)


_STEP_MATURITY = "truong_thanh"


def pre_maturity(steps, account, log) -> bool:
    """Kiểm tra step Trưởng Thành có được chọn hay không."""
    if _STEP_MATURITY not in steps:
        log(f"[{account.display_name}] Trưởng Thành: không có step được chọn; bỏ qua.")
        return False
    return True


def post_maturity(steps) -> list[str]:
    """Loại step Trưởng Thành sau khi quy trình hoàn tất."""
    if _STEP_MATURITY in steps:
        steps.remove(_STEP_MATURITY)
    return steps


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Chạy lần lượt pre → open → run → close → post."""
    if not pre_maturity(steps, account, log):
        return steps

    log(f"[{account.display_name}] Bắt đầu quy trình Trưởng Thành.")
    opened = False
    completed = False

    try:
        opened = task_open_maturity.run(
            worker, account, device, ocr_client, log
        )
        if not opened:
            log(f"[{account.display_name}] Không mở được Trưởng Thành; giữ nguyên step.")
            return steps

        completed = task_run_maturity.run(worker, account, device, log)
        if not completed:
            log(f"[{account.display_name}] Trưởng Thành chưa hoàn tất; giữ nguyên step.")
            return steps
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình Trưởng Thành phát sinh lỗi: {exc}")
        return steps
    finally:
        if opened:
            try:
                closed = task_close_maturity.run(worker, account, device, log)
                if not closed:
                    log(
                        f"[{account.display_name}] Không đóng được màn hình Trưởng Thành."
                    )
            except Exception as exc:
                log(f"[{account.display_name}] Lỗi khi đóng Trưởng Thành: {exc}")

    if completed:
        return post_maturity(steps)
    return steps
