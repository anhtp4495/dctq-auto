"""Tác vụ nhận lễ bao Quốc Vận trong nhóm Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.tasks.common.activity.perk.constants import (
    _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
)

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_TEMPLATE_NAMES = (
    _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
)


def _find_template(screen_bgr, templates, account, log):
    """Tìm template đầu tiên khớp theo thứ tự ưu tiên."""
    for template_name in _TEMPLATE_NAMES:
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
            return template_name, match
    return None, None


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Nhận lễ bao Quốc Vận bằng template matching và đệ quy sau khi click."""
    templates = get_templates(_TEMPLATE_NAMES)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Nhận lễ bao Quốc Vận đã dừng theo yêu cầu.")
        return False

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện lễ bao Quốc Vận: {exc}")
        return False

    template_name, match = _find_template(screen_bgr, templates, account, log)
    if template_name is None:
        log(
            f"[{account.username}] Không nhận diện được template lễ bao Quốc Vận; "
            "có thể đã chuyển sang màn hình khác."
        )
        return False

    if template_name == _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI:
        log(f"[{account.username}] Đã nhận lễ bao Quốc Vận.")
        return True

    try:
        _tap_match_center(device, match, account, log)
    except Exception as exc:
        log(f"[{account.username}] Không click được template {template_name}: {exc}")
        return False

    return run(
        worker, account, steps, device, ocr_client, log,
        screenshot=None,
    )
