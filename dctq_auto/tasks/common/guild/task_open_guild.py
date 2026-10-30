"""Thao tác dùng chung để mở màn hình [Quân đoàn]."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT,
    _TEMPLATE_QUAN_DOAN_CHAT_VAO_QUAN_DOAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


def open_guild(
    self, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở Quân đoàn bằng Template Matching; nhận screenshot có sẵn nếu được truyền vào."""

    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang mở màn hình [Quân đoàn].")
        return False

    log(f"[{account.username}] Bắt đầu mở màn hình [Quân đoàn].")

    template_names = (
        _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT,
        _TEMPLATE_QUAN_DOAN_CHAT_VAO_QUAN_DOAN,
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

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            log(
                f"[{account.username}] Đã xác nhận đang ở giao diện [Quân đoàn] "
                f"({template.id})."
            )
            return True

        if template_name in (
            _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT,
            _TEMPLATE_QUAN_DOAN_CHAT_VAO_QUAN_DOAN,
        ):
            x = round((match.left + match.right) / 2)
            y = round((match.top + match.bottom) / 2)
            action = (
                "mở chat Quân đoàn"
                if template_name == _TEMPLATE_MAIN_QUAN_DOAN_MO_CHAT
                else "Vào quân đoàn"
            )
            log(
                f"[{account.username}] Phát hiện nút {action}; "
                f"click trung điểm ({x}, {y}) rồi kiểm tra lại."
            )
            try:
                device.shell(f"input tap {x} {y}")
                time.sleep(1.0)
                return open_guild(self, account, device, ocr_client, log)
            except Exception as exc:
                log(f"[{account.username}] Mở màn hình [Quân đoàn] thất bại: {exc}")
                return False

    log(f"[{account.username}] Mở màn hình [Quân đoàn] thất bại.")
    return False


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới open_guild."""
    return open_guild(self, account, device, ocr_client, log, screenshot=screenshot)
