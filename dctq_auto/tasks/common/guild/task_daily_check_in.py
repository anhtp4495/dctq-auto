"""Điều phối tác vụ báo danh hằng ngày trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    #
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates
from dctq_auto.config.button_positions import ButtonPositions


def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step đóng góp Lương thảo."""
    if _STEP_QUAN_DOAN_BAO_DANH not in steps:
        return []

    return [
        _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
        _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
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
                grayscale=template.grayscale,
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


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm template báo danh tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Nhận diện trạng thái báo danh và thực hiện báo danh nếu chưa hoàn thành."""
    
    selected_steps = {
        step
        for step in (_STEP_QUAN_DOAN_BAO_DANH,)
        if step in steps
    }
    if not selected_steps:
        return steps

    template_names = get_template_names(steps)
    templates = get_templates(template_names)

    log(f"[{account.username}] Bắt đầu Báo danh Quân đoàn ...")
    if not worker._wait_if_paused():
        log(f"[{account.username}] =========================================")
        log(f"[{account.username}] Báo danh Quân đoàn đã dừng theo yêu cầu.")
        log(f"[{account.username}] =========================================")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình báo danh Quân đoàn: {exc}")
        return steps

    template_name, _, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name is None:
        log(
            f"[{account.username}] Không nhận diện được trạng thái báo danh "
            "Quân đoàn; chưa thể xác nhận hoàn thành."
        )
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_DA_BAO_DANH:
        log(f"[{account.username}] Đã báo danh.")
        _tap_match_center(device, match, account, log)
        log(f"[{account.username}] Đã xác nhận báo danh Quân đoàn thành công.")
        if _STEP_QUAN_DOAN_BAO_DANH in steps:
            steps.remove(_STEP_QUAN_DOAN_BAO_DANH)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
        tap_x, tap_y = ButtonPositions().get("quan_doan", "bao_danh")
        log(
            f"[{account.username}] Không phát hiện được templates - Click báo danh theo ButtonPositions tại ({tap_x}, {tap_y}); "
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        if _STEP_QUAN_DOAN_BAO_DANH in steps:
            steps.remove(_STEP_QUAN_DOAN_BAO_DANH)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH:
        log(f"[{account.username}] Chưa báo danh.")
        _tap_match_center(device, match, account, log)
        return run(worker, account, steps, device, ocr_client, log, screenshot=None)

    log(f"[{account.username}] =========================================")
    log(
        f"[{account.username}] Không nhận diện được trạng thái báo danh - Kết thúc [Báo danh Quân đoàn] "
    )
    log(f"[{account.username}] =========================================")
    return steps
