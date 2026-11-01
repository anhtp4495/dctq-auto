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


_MAX_TRY_CLOSE_SHOP = 5


def run(worker, account, device, ocr_client, log, screenshot=None, current_try=1) -> bool:
    """Đóng các lớp giao diện shop và xác nhận đã trở về màn hình chính."""
    if not worker._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang đóng [Cửa hàng].")
        return False

    template_names = (
        _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA,
        _TEMPLATE_CUA_HANG_DONG_MAN_HINH,
        _TEMPLATE_CUA_HANG_THUONG_THANH,
        _TEMPLATE_MAIN_CUA_HANG,
    )
    templates = get_templates(template_names)

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để đóng [Cửa hàng]: {exc}")
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

        if template_name == _TEMPLATE_MAIN_CUA_HANG:
            log(f"[{account.username}] Đã xác nhận đóng [Cửa hàng] thành công.")
            return True

        if current_try >= _MAX_TRY_CLOSE_SHOP:
            log(f"[{account.username}] Đã hết số lần thử đóng [Cửa hàng].")
            return False

        if template_name in (
            _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA,
            _TEMPLATE_CUA_HANG_DONG_MAN_HINH,
        ):
            x = round((match.left + match.right) / 2)
            y = round((match.top + match.bottom) / 2)
            action = (
                "đóng cửa sổ xác nhận mua"
                if template_name == _TEMPLATE_CUA_HANG_DONG_MAN_HINH_XAC_NHAN_MUA
                else "đóng màn hình cửa hàng"
            )
            log(f"[{account.username}] Phát hiện nút {action}; click trung tâm ({x}, {y}).")
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
            time.sleep(1.0)
        except Exception as exc:
            log(f"[{account.username}] Click đóng [Cửa hàng] thất bại: {exc}")
            return False

        return run(
            worker, account, device, ocr_client, log,
            screenshot=None, current_try=current_try + 1,
        )

    if current_try < _MAX_TRY_CLOSE_SHOP:
        log(
            f"[{account.username}] Chưa nhận diện được trạng thái [Cửa hàng]; "
            f"chụp lại lần {current_try + 1}."
        )
        time.sleep(0.7)
        return run(
            worker, account, device, ocr_client, log,
            screenshot=None, current_try=current_try + 1,
        )

    log(f"[{account.username}] Không xác nhận được đã đóng [Cửa hàng].")
    return False
