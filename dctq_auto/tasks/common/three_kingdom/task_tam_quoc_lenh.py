"""Điều phối mở giao diện và nhận thưởng Tam Quốc Lệnh."""

from dctq_auto.config.constants import _STEP_NHAN_THUONG_TAM_QUOC_LENH
from dctq_auto.tasks.common.three_kingdom import (
    task_open_tam_quoc_lenh,
    task_run_tam_quoc_lenh,
)


def pre_tam_quoc_lenh(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn nhận thưởng Tam Quốc Lệnh hay không."""
    if _STEP_NHAN_THUONG_TAM_QUOC_LENH not in steps:
        log("Tam Quốc Lệnh: không có step nhận thưởng trong danh sách; bỏ qua.")
        return False
    log("Tam Quốc Lệnh: tìm thấy step nhận thưởng; bắt đầu thực hiện.")
    return True


def post_tam_quoc_lenh(steps) -> list[str]:
    """Loại step sau khi mở giao diện và nhận thưởng thành công."""
    if _STEP_NHAN_THUONG_TAM_QUOC_LENH in steps:
        steps.remove(_STEP_NHAN_THUONG_TAM_QUOC_LENH)
    return steps


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Mở Tam Quốc Lệnh, nhận thưởng rồi cập nhật danh sách step còn lại."""
    if not pre_tam_quoc_lenh(steps, log):
        return steps

    log(f"[{account.display_name}] Bắt đầu quy trình Tam Quốc Lệnh.")
    try:
        opened = task_open_tam_quoc_lenh.run(
            worker, account, device, ocr_client, log
        )
        if not opened:
            log(f"[{account.display_name}] Không mở được Tam Quốc Lệnh; giữ nguyên step.")
            return steps

        received = task_run_tam_quoc_lenh.run(worker, account, device, log)
        if not received:
            log(f"[{account.display_name}] Nhận thưởng Tam Quốc Lệnh chưa hoàn tất; giữ nguyên step.")
            return steps

        return post_tam_quoc_lenh(steps)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình Tam Quốc Lệnh phát sinh lỗi: {exc}")
        return steps
