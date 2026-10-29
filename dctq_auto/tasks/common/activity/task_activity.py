"""Điều phối các bước thuộc màn hình Hoạt động."""

from dctq_auto.tasks.common.activity import task_close_activity, task_open_activity
from dctq_auto.tasks.common.activity.perk import (
    task_diem_danh,
    task_le_bao_quoc_van,
)


_ACTIVITY_STEPS = (
    (
        "hoat_dong_phuc_loi_diem_danh",
        "Điểm danh",
        task_diem_danh,
    ),
    (
        "hoat_dong_phuc_loi_le_bao_quoc_van",
        "Nhận lễ bao Quốc Vận",
        task_le_bao_quoc_van,
    ),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Hoạt động, chạy các bước được chọn, rồi luôn thử đóng màn hình.

    Các bước thành công được loại khỏi danh sách steps tại chỗ. Bước thất bại
    và các bước chưa chạy được giữ lại để luồng Clone có thể thử lại.
    """
    try:
        if not task_open_activity.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình Hoạt động; giữ nguyên các bước.")
            return steps

        for step_id, label, task_module in _ACTIVITY_STEPS:
            if step_id not in steps:
                continue

            try:
                log(f"[{account.username}] Bắt đầu bước Hoạt động: {label}.")
                success = bool(task_module.run(worker, device, ocr_client))
            except Exception as exc:
                log(f"[{account.username}] Bước Hoạt động {label} thất bại: {exc}")
                break

            if not success:
                log(f"[{account.username}] Giữ lại bước {step_id} để thử lại.")
                break

            steps.remove(step_id)
    finally:
        try:
            closed = task_close_activity.run(
                worker, account, device, ocr_client, log
            )
            if not closed:
                log(f"[{account.username}] Cảnh báo: chưa xác nhận đóng được màn hình Hoạt động.")
        except Exception as exc:
            log(f"[{account.username}] Lỗi khi đóng màn hình Hoạt động: {exc}")

    return steps
