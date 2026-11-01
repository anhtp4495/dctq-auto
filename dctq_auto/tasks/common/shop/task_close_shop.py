"""Thao tác dùng chung để đóng màn hình [Cửa hàng]."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_CUA_HANG,
    _TEMPLATE_CUA_HANG_THUONG_THANH,
    _TEMPLATE_CUA_HANG_DONG_MAN_HINH,
    _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_WAIT_MAIN_SCREEN_SECONDS = 10.0
_SCREEN_POLL_INTERVAL_SECONDS = 0.5


def run(worker, account, device, ocr_client, log, screenshot=None) -> bool:
    """Đóng các lớp giao diện shop và chờ xác nhận đã trở về màn hình chính."""
    template_names = (
        _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA,
        _TEMPLATE_CUA_HANG_DONG_MAN_HINH,
        _TEMPLATE_CUA_HANG_THUONG_THANH,
        _TEMPLATE_MAIN_CUA_HANG,
    )
    templates = get_templates(template_names)
    deadline = None

    while True:
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang đóng [Cửa hàng].")
            return False

        try:
            current_screenshot = screenshot if screenshot is not None else device.screenshot()
            screen_bgr = cv2.cvtColor(np.asarray(current_screenshot), cv2.COLOR_RGB2BGR)
            screenshot = None
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình để đóng [Cửa hàng]: {exc}")
            return False

        matched_template = None
        matched_result = None

        for template_name in template_names:
            template = templates.get(template_name)
            if template is None:
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
                matched_template = template_name
                matched_result = match
                report_template_match(
                    log, context=f"[{account.username}]", template=template, match=match
                )
                break

        if matched_template == _TEMPLATE_MAIN_CUA_HANG:
            log(f"[{account.username}] Đã xác nhận trở về giao diện chính sau khi đóng [Cửa hàng].")
            return True

        if matched_template is not None:
            if matched_template in (
                _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA,
                _TEMPLATE_CUA_HANG_DONG_MAN_HINH,
            ):
                x = round((matched_result.left + matched_result.right) / 2)
                y = round((matched_result.top + matched_result.bottom) / 2)
                action = (
                    "đóng cửa sổ xác nhận mua"
                    if matched_template == _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA
                    else "đóng màn hình cửa hàng"
                )
                log(
                    f"[{account.username}] Phát hiện nút {action}; "
                    f"click trung tâm ({x}, {y})."
                )
            else:
                try:
                    x, y = ButtonPositions().get("cua_hang", "dong_man_hinh")
                except (KeyError, ValueError) as exc:
                    log(f"[{account.username}] Không lấy được tọa độ đóng [Cửa hàng]: {exc}")
                    return False
                log(
                    f"[{account.username}] Đang ở [Thương Thành]; "
                    f"click buttonlocations cua_hang.dong_man_hinh tại ({x}, {y})."
                )

            try:
                device.shell(f"input tap {x} {y}")
            except Exception as exc:
                log(f"[{account.username}] Click đóng [Cửa hàng] thất bại: {exc}")
                return False

            if deadline is None:
                deadline = time.monotonic() + _MAX_WAIT_MAIN_SCREEN_SECONDS

            time.sleep(_SCREEN_POLL_INTERVAL_SECONDS)
            continue

        if deadline is None:
            log(f"[{account.username}] Không xác định được trạng thái hiện tại của [Cửa hàng].")
            return False

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            log(
                f"[{account.username}] Hết {_MAX_WAIT_MAIN_SCREEN_SECONDS:.0f} giây "
                "nhưng chưa xác nhận được đã trở về giao diện chính."
            )
            return False

        log(
            f"[{account.username}] Đang chờ giao diện chính sau khi đóng [Cửa hàng] "
            f"(còn tối đa {remaining:.1f} giây)."
        )
        time.sleep(min(_SCREEN_POLL_INTERVAL_SECONDS, remaining))
