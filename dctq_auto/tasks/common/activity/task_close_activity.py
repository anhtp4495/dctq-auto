"""Thao tác dùng chung để đóng màn hình Hoạt động / Phúc Lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_HOAT_DONG,
    _TEMPLATE_DANG_CHON_PHUC_LOI,
    _TEMPLATE_DANG_CHON_HOAT_DONG,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates
from dctq_auto.config.button_positions import ButtonPositions


def close_activity(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Đóng Hoạt động bằng Template Matching; nhận screenshot có sẵn nếu được truyền vào."""
    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang đóng màn hình [Hoạt động].")
        return False

    log(f"[{account.username}] Bắt đầu kiểm tra đóng màn hình [Hoạt động].")

    template_names = (
        _TEMPLATE_MAIN_HOAT_DONG,
        _TEMPLATE_DANG_CHON_PHUC_LOI,
        _TEMPLATE_DANG_CHON_HOAT_DONG,
    )
    templates = get_templates(template_names)

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện Hoạt động: {exc}")
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
            log,
            context=f"[{account.username}]",
            template=template,
            match=match,
        )

        if template_name == _TEMPLATE_MAIN_HOAT_DONG:
            log(f"[{account.username}] Đã xác nhận đóng màn hình [Hoạt động] thành công.")
            return True

        if template_name in (_TEMPLATE_DANG_CHON_PHUC_LOI, _TEMPLATE_DANG_CHON_HOAT_DONG):
            try:
                x, y = ButtonPositions().get("hoat_dong", "dong_man_hinh")
                log(
                    f"[{account.username}] Màn hình Hoạt động vẫn đang mở "
                    f"({template.id}); click đóng màn hình tại ({x}, {y}) "
                )
                device.shell(f"input tap {x} {y}")
                time.sleep(1.0)
                return close_activity(self, account, device, ocr_client, log)
            except Exception as exc:
                log(f"[{account.username}] Đóng màn hình Hoạt động thất bại: {exc}")
                return False

    log(f"[{account.username}] Không xác định được trạng thái màn hình Hoạt động.")
    return False


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới close_activity."""
    return close_activity(self, account, device, ocr_client, log, screenshot=screenshot)
