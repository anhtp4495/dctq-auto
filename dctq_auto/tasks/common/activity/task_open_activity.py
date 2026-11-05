"""Thao tác dùng chung để mở màn hình [Hoạt động]."""

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
from dctq_auto.tasks.common.close_knowned_dialog import close_knowned_dialog


_MAX_TRIES = 10


def open_activity(
    self, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở Hoạt động bằng Template Matching, thử nhận diện tối đa _MAX_TRIES lần."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình [Hoạt động].")

    template_names = (
        _TEMPLATE_MAIN_HOAT_DONG,
        _TEMPLATE_DANG_CHON_PHUC_LOI,
        _TEMPLATE_DANG_CHON_HOAT_DONG,
    )
    templates = get_templates(template_names)

    for attempt in range(1, _MAX_TRIES + 1):
        if not self._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang mở màn hình [Hoạt động].")
            return False

        try:
            current_screenshot = screenshot if attempt == 1 and screenshot is not None else device.screenshot()
            screen_bgr = cv2.cvtColor(np.asarray(current_screenshot), cv2.COLOR_RGB2BGR)
        except Exception as exc:
            log(
                f"[{account.display_name}] Không chụp được màn hình để nhận diện "
                f"Hoạt động (lần thử {attempt}/{_MAX_TRIES}): {exc}"
            )
            if attempt < _MAX_TRIES:
                time.sleep(1.0)
                continue
            return False

        retry = False
        for template_name in template_names:
            template = templates.get(template_name)
            if template is None:
                log(f"[{account.display_name}] Không tải được template {template_name}; bỏ qua.")
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
                log(f"[{account.display_name}] Lỗi template matching {template_name}: {exc}")
                continue

            if match is None:
                continue

            report_template_match(
                log,
                context=f"[{account.display_name}]",
                template=template,
                match=match,
            )

            if template_name in (_TEMPLATE_DANG_CHON_PHUC_LOI, _TEMPLATE_DANG_CHON_HOAT_DONG):
                log(
                    f"[{account.display_name}] Đã xác nhận màn hình [Hoạt động] "
                    f"({template.id}) ở lần thử {attempt}/{_MAX_TRIES}."
                )
                return True

            if template_name == _TEMPLATE_MAIN_HOAT_DONG:
                x = round((match.left + match.right) / 2)
                y = round((match.top + match.bottom) / 2)
                log(
                    f"[{account.display_name}] Phát hiện [Hoạt động] ở [Màn hình chính]; "
                    f"click trung điểm ({x}, {y}) rồi kiểm tra lại "
                    f"(lần thử {attempt}/{_MAX_TRIES})."
                )
                try:
                    device.shell(f"input tap {x} {y}")
                except Exception as exc:
                    log(f"[{account.display_name}] Mở màn hình [Hoạt động] thất bại: {exc}")
                    return False
                retry = True
                break

        if attempt < _MAX_TRIES:
            if not retry:
                log(
                    f"[{account.display_name}] Chưa nhận diện được màn hình [Hoạt động]; "
                    f"thử lại ({attempt + 1}/{_MAX_TRIES})."
                )
                close_knowned_dialog(
                    self, account, device, ocr_client, log, screen_bgr
                )
            time.sleep(1.0)

    log(f"[{account.display_name}] Mở màn hình [Hoạt động] thất bại sau {_MAX_TRIES} lần thử.")
    return False


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới open_activity."""
    return open_activity(self, account, device, ocr_client, log, screenshot=screenshot)
