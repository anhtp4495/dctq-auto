"""Mua Quẻ lành trong [Cửa hàng Danh Vọng]."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH,
    _TEMPLATE_CUA_HANG_DANH_VONG,
    _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG,
    _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH,
    _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH,
    _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRY_BUY_FORTUNE_LOT = 10


def _find_template(screen_bgr, templates, template_names, account, log):
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
        if match is not None:
            report_template_match(log, context=f"[{account.username}]", template=template, match=match)
            return template_name, match
    return None, None


def _tap_match(device, match, account, log, description):
    x = round((match.left + match.right) / 2)
    y = round((match.top + match.bottom) / 2)
    log(f"[{account.username}] Click {description} tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.8)


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
    current_try=1, purchase_submitted=False, item_opened=False,
) -> list[str]:
    """Mở Danh Vọng, mua Quẻ lành một lần và xác nhận trạng thái đã mua."""
    if _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH not in steps:
        return steps
    if not worker._wait_if_paused():
        log(f"[{account.username}] Mua Quẻ lành đã dừng theo yêu cầu.")
        return steps

    template_names = (
        _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_DANH_VONG,
        _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG,
    )
    templates = get_templates(template_names)
    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để mua Quẻ lành: {exc}")
        return steps

    template_name, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name == _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH:
        log(f"[{account.username}] Quẻ lành đã được mua; hoàn tất step.")
        steps.remove(_STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH)
        return steps

    if template_name == _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH:
        if purchase_submitted:
            try:
                close_x, close_y = ButtonPositions().get(
                    "cua_hang.chien_tranh.danh_vong", "dong_man_hinh"
                )
                log(f"[{account.username}] Hộp mua vẫn còn mở sau xác nhận; đóng tại ({close_x}, {close_y}).")
                device.shell(f"input tap {close_x} {close_y}")
                time.sleep(0.8)
            except Exception as exc:
                log(f"[{account.username}] Không đóng được hộp mua Quẻ lành: {exc}")
                return steps
            return run(
                worker, account, steps, device, ocr_client, log,
                screenshot=None, current_try=current_try + 1,
                purchase_submitted=True, item_opened=item_opened,
            )

        try:
            plus_x, plus_y = ButtonPositions().get(
                "cua_hang.chien_tranh.danh_vong", "tang_so_luong"
            )
            confirm_x, confirm_y = ButtonPositions().get(
                "cua_hang.chien_tranh.danh_vong", "xac_nhan"
            )
            log(f"[{account.username}] Màn hình mua Quẻ lành đã mở; tăng số lượng tại ({plus_x}, {plus_y}).")
            device.shell(f"input tap {plus_x} {plus_y}")
            time.sleep(0.5)
            log(f"[{account.username}] Xác nhận mua Quẻ lành tại ({confirm_x}, {confirm_y}).")
            device.shell(f"input tap {confirm_x} {confirm_y}")
            time.sleep(1.2)
        except Exception as exc:
            log(f"[{account.username}] Thao tác xác nhận mua Quẻ lành thất bại: {exc}")
            return steps
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, current_try=current_try + 1,
            purchase_submitted=True, item_opened=item_opened,
        )

    if template_name == _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH:
        if purchase_submitted:
            log(f"[{account.username}] Đã gửi yêu cầu mua nhưng chưa xác nhận được Quẻ lành; giữ lại step.")
            return steps
        if item_opened:
            if current_try < _MAX_TRY_BUY_FORTUNE_LOT:
                time.sleep(0.7)
                return run(
                    worker, account, steps, device, ocr_client, log,
                    screenshot=None, current_try=current_try + 1,
                    item_opened=True,
                )
            log(f"[{account.username}] Đã mở sản phẩm nhưng không nhận diện được hộp mua Quẻ lành; giữ lại step.")
            return steps
        _tap_match(device, match, account, log, "sản phẩm [Quẻ lành]")
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, current_try=current_try + 1, item_opened=True,
        )

    if template_name == _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG:
        _tap_match(device, match, account, log, "lối vào [Shop Danh Vọng]")
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, current_try=current_try + 1,
        )

    if template_name == _TEMPLATE_CUA_HANG_DANH_VONG:
        log(f"[{account.username}] Đã vào [Shop Danh Vọng] nhưng chưa nhận diện được trạng thái sản phẩm Quẻ lành.")
        return steps

    if current_try < _MAX_TRY_BUY_FORTUNE_LOT:
        log(f"[{account.username}] Chưa nhận diện được trạng thái mua Quẻ lành; thử lại {current_try}/{_MAX_TRY_BUY_FORTUNE_LOT}.")
        time.sleep(0.7)
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, current_try=current_try + 1,
            purchase_submitted=purchase_submitted, item_opened=item_opened,
        )

    log(f"[{account.username}] Không xác định được trạng thái [Mua quẻ lành]; giữ lại step.")
    return steps
