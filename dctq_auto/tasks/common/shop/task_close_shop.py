"""Thao tác dùng chung để đóng màn hình [Cửa hàng]."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import _TEMPLATE_MAIN_CUA_HANG
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRY_CLOSE_SHOP = 5


def run(worker, account, device, ocr_client, log, screenshot=None, current_try=1) -> bool:
    """Dùng phím Back để thoát shop, xác nhận đã trở về màn hình chính."""
    if not worker._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang đóng [Cửa hàng].")
        return False

    template = get_templates((_TEMPLATE_MAIN_CUA_HANG,)).get(_TEMPLATE_MAIN_CUA_HANG)
    if template is None:
        log(f"[{account.username}] Không tải được template {_TEMPLATE_MAIN_CUA_HANG}.")
        return False
    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
        match = match_template(
            screen_bgr, template.image, threshold=template.threshold,
            method=template.method, search_rect=template.search_rect,
            grayscale=template.grayscale,
        )
    except Exception as exc:
        log(f"[{account.username}] Không nhận diện được trạng thái khi đóng [Cửa hàng]: {exc}")
        return False

    if match is not None:
        report_template_match(log, context=f"[{account.username}]", template=template, match=match)
        log(f"[{account.username}] Đã xác nhận thoát [Cửa hàng], trở về màn hình chính.")
        return True

    if current_try >= _MAX_TRY_CLOSE_SHOP:
        log(f"[{account.username}] Không xác nhận được đã thoát [Cửa hàng].")
        return False

    log(f"[{account.username}] Shop vẫn đang mở; nhấn Back lần {current_try}.")
    try:
        device.shell("input keyevent 4")
        time.sleep(1.0)
    except Exception as exc:
        log(f"[{account.username}] Không thể nhấn Back để đóng [Cửa hàng]: {exc}")
        return False
    return run(worker, account, device, ocr_client, log, screenshot=None, current_try=current_try + 1)
