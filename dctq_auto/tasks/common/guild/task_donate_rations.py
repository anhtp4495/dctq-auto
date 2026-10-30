"""Điều phối tác vụ đóng góp Lương thảo trong màn hình Quân đoàn."""

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_XAC_NHAN_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_1,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_2,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_XAC_NHAN_LAY_THEM_LUONG_THAO,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step đóng góp Lương thảo."""
    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO not in steps:
        return []

    return [
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
        _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
        _TEMPLATE_QUAN_DOAN_XAC_NHAN_DONG_GOP_LUONG_THAO,
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_1,
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_2,
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
        _TEMPLATE_QUAN_DOAN_XAC_NHAN_LAY_THEM_LUONG_THAO,
    ]


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


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Nhận diện trạng thái đóng góp Lương thảo.

    Đây là khung điều phối theo cấu trúc task_perk.py. Phần thao tác click và
    xác nhận sẽ được bổ sung sau khi hoàn thiện flow thực tế.
    """
    selected_steps = {
        step
        for step in (_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,)
        if step in steps
    }
    if not selected_steps:
        return steps

    template_names = get_template_names(steps)
    templates = get_templates(template_names)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Đóng góp Lương thảo đã dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình đóng góp Lương thảo: {exc}")
        return steps

    template_name, _, _ = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name is None:
        log(
            f"[{account.username}] Không nhận diện được trạng thái đóng góp "
            "Lương thảo; giữ lại step để thử lại."
        )
        return steps

    log(
        f"[{account.username}] Đã nhận diện trạng thái {template_name}; "
        "khung thao tác đóng góp Lương thảo đang chờ hoàn thiện."
    )
    return steps
