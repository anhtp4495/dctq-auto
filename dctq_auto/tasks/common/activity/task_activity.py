"""Điều phối các bước thuộc màn hình Hoạt động."""

from dctq_auto.tasks.common.activity import task_close_activity, task_open_activity
from dctq_auto.tasks.common.activity.perk import task_perk


_PERK_STEP_IDS = {
    "hoat_dong_phuc_loi_diem_danh",
    "hoat_dong_phuc_loi_le_bao_quoc_van",
}


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Hoạt động, chạy nhóm Phúc lợi được chọn, rồi luôn thử đóng màn hình.

    Các bước thành công được loại khỏi danh sách steps tại chỗ. Bước thất bại
    và các bước chưa chạy được giữ lại để luồng Clone có thể thử lại.
    """
    activity_open_attempted = False
    try:
        selected_perk_steps = _PERK_STEP_IDS.intersection(steps)
        if not selected_perk_steps:
            return steps

        activity_open_attempted = True
        if not task_open_activity.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình Hoạt động; giữ nguyên các bước.")
            return steps

        task_perk.run(worker, account, steps, device, ocr_client, log)
    finally:
        if activity_open_attempted:
            try:
                closed = task_close_activity.run(
                    worker, account, device, ocr_client, log
                )
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận đóng được màn hình Hoạt động.")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi đóng màn hình Hoạt động: {exc}")

    return steps
