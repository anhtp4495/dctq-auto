"""Điều phối các bước thuộc màn hình [Quân đoàn]."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.tasks.common.guild import (
    task_blessing,
    task_close_guild,
    task_daily_check_in,
    task_donate_rations,
    task_knb,
    task_lucky_bag,
    task_open_guild,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_GUILD_STEP_IDS = {
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
}


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Quân đoàn, chạy các bước được chọn, rồi đóng màn hình.

    Các bước thành công được loại khỏi danh sách steps tại chỗ. Bước thất bại
    và các bước chưa chạy được giữ lại để luồng Clone có thể thử lại.
    """
    guild_open_attempted = False
    try:
        selected_steps = _GUILD_STEP_IDS.intersection(steps)
        if not selected_steps:
            return steps

        guild_open_attempted = True
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình [Quân đoàn]; giữ nguyên các bước.")
            return steps

        steps_run(worker, account, steps, device, ocr_client, log, screenshot=screenshot)
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")

    return steps


# Số lần tối đa xác định game đã tải thành công
_MAX_TRY_DETECT_MAIN_SCREEN = 3

def steps_run(worker, account, steps, device, ocr_client, log, screenshot=None, current_try: int = 1) -> list[str]:
    """Nhận diện trạng thái Quân đoàn và chạy các step có thể xác định."""

    selected_steps = {step for step in _GUILD_STEP_IDS if step in steps}
    if not selected_steps:
        return steps

    if _STEP_QUAN_DOAN_BAO_DANH in selected_steps:
        try:
            steps = task_daily_check_in.run(
                worker, account, steps, device, ocr_client, log
            )
        except Exception as exc:
            log(f"[{account.username}] Báo danh Quân đoàn thất bại: {exc}")
            return steps

    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in selected_steps:
        try:
            steps = task_donate_rations.run(
                worker, account, steps, device, ocr_client, log
            )
        except Exception as exc:
            log(f"[{account.username}] Đóng góp lương thảo thất bại: {exc}")
            return steps

    if current_try < _MAX_TRY_DETECT_MAIN_SCREEN:
        worker.log_message.emit(f"[{account.username}] [Quân đoàn] Chưa chạy xong - Thử lại lần {current_try}.")
        time.sleep(1.5)
        return steps_run(worker, account, steps, device, ocr_client, log, screenshot=None, current_try=current_try + 1)

    steps_to_remove = _GUILD_STEP_IDS.intersection(steps)
    for step in steps_to_remove:
        steps.remove(step)
    if steps_to_remove:
        log(
            f"[{account.username}] Đã thử lại {current_try} lần; "
            f"Các step chưa hoàn tất: {', '.join(sorted(steps_to_remove))}."
        )
    return steps

def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step Quân đoàn được chọn."""
    template_names = []

    if _STEP_QUAN_DOAN_BAO_DANH in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
            _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
        ))

    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
            _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
        ))

    if _STEP_QUAN_DOAN_DONG_GOP_KNB in steps:
        template_names.append(_TEMPLATE_QUAN_DOAN_DONG_GOP_KNB)

    if _STEP_QUAN_DOAN_TUI_PHUC in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
            _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
        ))

    if _STEP_QUAN_DOAN_CAU_VAN in steps:
        template_names.append(_TEMPLATE_QUAN_DOAN_CAU_VAN)

    template_names.append(_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH)
    return template_names


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template khớp đầu tiên theo thứ tự ưu tiên."""
    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            log(f"[{account.username}] Không tải được template {template_name}; bỏ qua.")
            continue
        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=template.search_rect,
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.username}] Lỗi template matching {template_name}: {exc}")
            continue
        if match is not None:
            report_template_match(
                log,
                context=f"[{account.username}]",
                template=template,
                match=match,
            )
            return template_name, template, match
    return None, None, None
