"""Đóng tab [Shop Chiến Tranh] và xác nhận đã rời giao diện này."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_CUA_HANG_THUONG_THANH,
    _TEMPLATE_MAIN_CUA_HANG,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRY_CLOSE_SHOP_WAR = 5


def run(worker, account, device, ocr_client, log, screenshot=None, current_try=1) -> bool:
    """Thoát tab Shop Chiến Tranh và xác nhận đã rời giao diện này."""
    if not worker._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đóng [Shop Chiến Tranh].")
        return False

    template_names = (
        _TEMPLATE_CUA_HANG_THUONG_THANH,
        _TEMPLATE_MAIN_CUA_HANG,
    )
    templates = get_templates(template_names)

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình khi đóng [Shop Chiến Tranh]: {exc}")
        return False

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

        if match is None:
            continue

        report_template_match(
            log, context=f"[{account.username}]", template=template, match=match
        )
        if template_name == _TEMPLATE_CUA_HANG_THUONG_THANH:
            log(f"[{account.username}] Đã thoát [Shop Chiến Tranh], trở về [Thương Thành].")
        else:
            log(f"[{account.username}] Đã thoát [Shop Chiến Tranh]; giao diện cửa hàng đã đóng.")
        return True

    if current_try >= _MAX_TRY_CLOSE_SHOP_WAR:
        log(f"[{account.username}] Không xác nhận được đã thoát [Shop Chiến Tranh].")
        return False

    log(
        f"[{account.username}] Vẫn đang ở [Shop Chiến Tranh] hoặc chưa xác định được; "
        f"nhấn Back lần {current_try}."
    )
    try:
        device.shell("input keyevent 4")
        time.sleep(1.0)
    except Exception as exc:
        log(f"[{account.username}] Không thể nhấn Back để đóng [Shop Chiến Tranh]: {exc}")
        return False

    return run(
        worker, account, device, ocr_client, log,
        screenshot=None, current_try=current_try + 1,
    )
