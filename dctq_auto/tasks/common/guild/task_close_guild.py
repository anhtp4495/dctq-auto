"""Thao tác dùng chung để đóng màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT,
    _TEMPLATE_QUAN_DOAN_CHAT_TAT_CHAT,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates
from dctq_auto.config.button_positions import ButtonPositions


def close_guild(
    self, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Đóng Quân đoàn bằng Template Matching; nhận screenshot có sẵn nếu được truyền vào."""

    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang đóng màn hình [Quân đoàn].")
        return False

    log(f"[{account.username}] Bắt đầu kiểm tra đóng màn hình [Quân đoàn].")

    template_names = (
        _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT,
        _TEMPLATE_QUAN_DOAN_CHAT_TAT_CHAT,
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    )
    templates = get_templates(template_names)

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện Quân đoàn: {exc}")
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

        if template_name == _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT:
            log(f"[{account.username}] Đã xác nhận đóng màn hình [Quân đoàn] thành công.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            try:
                x, y = ButtonPositions().get("quan_doan", "dong_man_hinh")
                log(
                    f"[{account.username}] Đang ở giao diện Quân đoàn "
                    f"({template.id}); click đóng màn hình tại ({x}, {y})."
                )
                device.shell(f"input tap {x} {y}")
                time.sleep(1.0)
                return close_guild(self, account, device, ocr_client, log)
            except Exception as exc:
                log(f"[{account.username}] Đóng màn hình Quân đoàn thất bại: {exc}")
                return False

        if template_name == _TEMPLATE_QUAN_DOAN_CHAT_TAT_CHAT:
            x = round((match.left + match.right) / 2)
            y = round((match.top + match.bottom) / 2)
            log(
                f"[{account.username}] Phát hiện nút tắt chat Quân đoàn "
                f"({template.id}); click trung điểm ({x}, {y}) rồi kiểm tra lại."
            )
            try:
                device.shell(f"input tap {x} {y}")
                time.sleep(1.0)
                return close_guild(self, account, device, ocr_client, log)
            except Exception as exc:
                log(f"[{account.username}] Đóng chat Quân đoàn thất bại: {exc}")
                return False

    log(f"[{account.username}] Không xác định được trạng thái màn hình Quân đoàn.")
    return False


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới close_guild."""
    return close_guild(self, account, device, ocr_client, log, screenshot=screenshot)
