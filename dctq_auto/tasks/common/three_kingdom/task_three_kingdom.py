"""Điều phối mở giao diện và nhận thưởng Tam Quốc Lệnh."""

from dctq_auto.config.constants import (
    _STEP_NHAN_THUONG_TAM_QUOC_LENH,
    _TEMPLATE_MAIN_CHUA_NHAN_TAM_QUOC_LENH,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.three_kingdom import (
    task_close_three_kingdom,
    task_open_three_kingdom,
    task_run_three_kingdom,
)
from dctq_auto.vision.template_store import get_templates


def pre_three_kingdom(steps, account, device, log) -> bool:
    """Kiểm tra step và bỏ qua nếu Tam Quốc Lệnh đã nhận thưởng."""
    if _STEP_NHAN_THUONG_TAM_QUOC_LENH not in steps:
        log("Tam Quốc Lệnh: không có step nhận thưởng trong danh sách; bỏ qua.")
        return False


    try:
        templates = get_templates((_TEMPLATE_MAIN_CHUA_NHAN_TAM_QUOC_LENH,))
        template = templates.get(_TEMPLATE_MAIN_CHUA_NHAN_TAM_QUOC_LENH)
        screen = screen_bgr(device)
    except Exception as exc:
        log(
            f"[{account.display_name}] Không chụp được màn hình để kiểm tra "
            f"trạng thái Tam Quốc Lệnh: {exc}; tiếp tục quy trình."
        )
        return True

    if match(screen, template, account=account, log=log) is not None:
        log(f"[{account.display_name}] Chưa nhận thưởng Tam Quốc Lệnh; bắt đầu thực hiện.")
        return True
    
    log(
        f"[{account.display_name}] Tam Quốc Lệnh đã nhận thưởng; "
        "loại step và bỏ qua."
    )
    steps.remove(_STEP_NHAN_THUONG_TAM_QUOC_LENH)
    return False


def post_three_kingdom(steps) -> list[str]:
    """Loại step sau khi nhận thưởng thành công."""
    if _STEP_NHAN_THUONG_TAM_QUOC_LENH in steps:
        steps.remove(_STEP_NHAN_THUONG_TAM_QUOC_LENH)
    return steps


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Mở Tam Quốc Lệnh, nhận thưởng rồi cập nhật danh sách step còn lại."""
    try:
        if not pre_three_kingdom(steps, account, device, log):
            return steps

        log(f"[{account.display_name}] Bắt đầu quy trình Tam Quốc Lệnh.")
        opened = task_open_three_kingdom.run(
            worker, account, device, ocr_client, log
        )
        if not opened:
            log(f"[{account.display_name}] Không mở được Tam Quốc Lệnh; giữ nguyên step.")
            return steps

        received = task_run_three_kingdom.run(worker, account, device, log)
        if not received:
            log(f"[{account.display_name}] Nhận thưởng Tam Quốc Lệnh chưa hoàn tất; giữ nguyên step.")
            return steps

        closed = task_close_three_kingdom.run(worker, account, device, log)
        if not closed:
            log(
                f"[{account.display_name}] Đã nhận thưởng Tam Quốc Lệnh nhưng "
                "không đóng được màn hình; vẫn hoàn tất step nhận thưởng."
            )

        return post_three_kingdom(steps)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình Tam Quốc Lệnh phát sinh lỗi: {exc}")
        return steps
