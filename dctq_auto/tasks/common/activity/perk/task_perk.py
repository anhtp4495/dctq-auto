"""Điều phối các tác vụ thuộc mục Hoạt động - Phúc lợi."""

from dctq_auto.tasks.common.activity.perk import (
    task_diem_danh,
    task_le_bao_quoc_van,
)


_PERK_STEPS = (
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


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Chạy các tác vụ Phúc lợi được chọn; giữ lại bước lỗi để có thể thử lại."""
    for step_id, label, task_module in _PERK_STEPS:
        if step_id not in steps:
            continue

        try:
            log(f"[{account.username}] Bắt đầu bước Phúc lợi: {label}.")
            success = bool(task_module.run(worker, device, ocr_client))
        except Exception as exc:
            log(f"[{account.username}] Bước Phúc lợi {label} thất bại: {exc}")
            break

        if not success:
            log(f"[{account.username}] Giữ lại bước {step_id} để thử lại.")
            break

        steps.remove(step_id)

    return steps
