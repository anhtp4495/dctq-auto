"""Điều phối các tác vụ thuộc giao diện Chiến Tranh."""

from dctq_auto.tasks.common.stage_defense import task_stage_defense
from dctq_auto.tasks.common.war import task_close_war


def pre_war(steps, log) -> bool:
    """Kiểm tra có step chiến tranh nào đã được triển khai và được chọn không."""
    return task_stage_defense.pre_stage_defense(steps, log)


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Chạy Mưu Binh (tự mở Chiến Tranh khi cần), rồi đóng giao diện."""
    if not pre_war(steps, log):
        return steps

    try:
        task_stage_defense.run(worker, account, device, ocr_client, log)
    finally:
        if not task_close_war.run(worker, account, device, log):
            log(f"[{account.display_name}] Cảnh báo: chưa xác nhận đóng được màn hình Chiến Tranh.")

    return steps
