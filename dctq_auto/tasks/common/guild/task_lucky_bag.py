"""Điều phối tác vụ nhận Túi phúc trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


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


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm template Túi phúc tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Nhận diện trạng thái Túi phúc và nhận nếu chưa nhận."""
    if _STEP_QUAN_DOAN_TUI_PHUC not in steps:
        return steps

    template_names = (
        _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
        _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
    )
    templates = get_templates(template_names)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Nhận Túi phúc Quân đoàn đã dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình Túi phúc Quân đoàn: {exc}")
        return steps

    template_name, _, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name is None:
        log(
            f"[{account.username}] Không nhận diện được trạng thái Túi phúc "
            "Quân đoàn; giữ lại step để thử lại."
        )
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC:
        log(f"[{account.username}] Đã xác nhận nhận Túi phúc Quân đoàn thành công.")
        steps.remove(_STEP_QUAN_DOAN_TUI_PHUC)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC:
        _tap_match_center(device, match, account, log)
        return run(worker, account, steps, device, ocr_client, log, screenshot=None)

    return steps
