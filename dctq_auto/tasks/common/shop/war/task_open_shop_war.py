"""Mở tab [Shop Chiến Tranh] trong giao diện Cửa hàng."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_CUA_HANG_SHOP_CHIEN_TRANH,
    _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRY_OPEN_SHOP_WAR = 5


def run(worker, account, steps, device, ocr_client, log, screenshot=None, current_try=1) -> bool:
    """Chọn Shop Chiến Tranh và xác nhận tab đã được mở."""
    if not worker._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi mở [Shop Chiến Tranh].")
        return False

    template_names = (
        _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH,
        _TEMPLATE_CUA_HANG_SHOP_CHIEN_TRANH,
    )
    templates = get_templates(template_names)
    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình [Shop Chiến Tranh]: {exc}")
        return False

    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            log(f"[{account.username}] Không tải được template {template_name}; bỏ qua.")
            continue
        try:
            match = match_template(
                screen_bgr, template.image, threshold=template.threshold,
                method=template.method, search_rect=template.search_rect,
                grayscale=template.grayscale,
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.username}] Lỗi template matching {template_name}: {exc}")
            continue
        if match is None:
            continue

        report_template_match(log, context=f"[{account.username}]", template=template, match=match)
        if template_name == _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH:
            log(f"[{account.username}] Đã xác nhận đang ở [Shop Chiến Tranh].")
            return True

        x = round((match.left + match.right) / 2)
        y = round((match.top + match.bottom) / 2)
        log(f"[{account.username}] Click tab [Shop Chiến Tranh] tại ({x}, {y}).")
        try:
            device.shell(f"input tap {x} {y}")
            time.sleep(1.0)
            return run(worker, account, steps, device, ocr_client, log, screenshot=None, current_try=current_try + 1)
        except Exception as exc:
            log(f"[{account.username}] Mở [Shop Chiến Tranh] thất bại: {exc}")
            return False

    if current_try < _MAX_TRY_OPEN_SHOP_WAR:
        log(f"[{account.username}] Chưa nhận diện được [Shop Chiến Tranh]; thử lại.")
        time.sleep(0.7)
        return run(worker, account, steps, device, ocr_client, log, screenshot=None, current_try=current_try + 1)

    log(f"[{account.username}] Không mở/xác nhận được [Shop Chiến Tranh].")
    return False
