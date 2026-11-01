"""Điều phối tác vụ [Cửa hàng Danh Vọng - Mua quẻ lành]."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH,
    _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH,
    _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG,
    _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH,
    _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH,
    _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_SWIPE_FORTUNE_LOT = 2
_MAX_TRY_BUY_FORTUNE_LOT = 3


def _finish_step(steps, account, log):
    """Kết thúc step mua Quẻ lành."""
    log(f"[{account.username}] [Quẻ lành] đã mua; kết thúc tác vụ.")
    if _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH in steps:
        steps.remove(_STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH)
    return steps


def _find_template(screen_bgr, templates, template_names, account, log):
    """Tìm template theo thứ tự ưu tiên và trả về kết quả khớp đầu tiên."""
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

        if match is not None:
            report_template_match(
                log,
                context=f"[{account.username}]",
                template=template,
                match=match,
            )
            return template_name, template, match

    return None, None, None


def _run(
    worker, account, steps, device, ocr_client, log, screenshot,
    templates, swipe_positions, fortune_clicked=False, buy_try_count=0,
) -> list[str]:
    """Tìm Quẻ lành; cuộn tối đa hai lần cho đến khi thấy trạng thái mua."""
    step = _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH
    if step not in steps:
        return steps

    if not worker._wait_if_paused():
        log(f"[{account.username}] Mua [Quẻ lành] đã dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình [Mua quẻ lành]: {exc}")
        return steps

    # Ưu tiên hai trạng thái của Quẻ lành để dừng cuộn ngay khi tìm thấy.
    template_names = (
        _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG,
        _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH,
        _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH,
    )
    template_name, template, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )

    if template_name is None:
        log(f"[{account.username}] Không nhận diện được trạng thái [Mua quẻ lành]; giữ lại step.")
        return steps

    if template_name == _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH:
        swipe_positions.clear()
        return _finish_step(steps, account, log)

    if template_name == _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH:
        swipe_positions.clear()
        if fortune_clicked:
            log(
                f"[{account.username}] Đã click [Quẻ lành] nhưng màn hình vẫn báo chưa mua; "
                "không click lặp, giữ lại step."
            )
            return steps

        x = (match.left + match.right) // 2
        y = match.bottom - 1
        log(f"[{account.username}] Click sát đáy template [Quẻ lành] tại ({x}, {y}).")
        try:
            device.shell(f"input tap {x} {y}")
            time.sleep(0.8)
        except Exception as exc:
            log(f"[{account.username}] Click [Quẻ lành] thất bại: {exc}")
            return steps

        return _run(
            worker, account, steps, device, ocr_client, log, None,
            templates, swipe_positions, fortune_clicked=True,
            buy_try_count=buy_try_count,
        )

    if template_name == _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG:
        if not swipe_positions:
            log(
                f"[{account.username}] Đã vuốt tìm [Quẻ lành] đủ "
                f"{_MAX_SWIPE_FORTUNE_LOT} lần; không vuốt thêm."
            )
            return steps

        start_x, start_y = ButtonPositions().get(
            "cua_hang.chien_tranh.danh_vong", "cua_hang_danh_vong_item2"
        )
        end_x, end_y = ButtonPositions().get(
            "cua_hang.chien_tranh.danh_vong", "cua_hang_danh_vong_item1"
        )
        swipe_number = _MAX_SWIPE_FORTUNE_LOT - len(swipe_positions) + 1
        log(
            f"[{account.username}] Vuốt Shop Danh Vọng từ ({start_x}, {start_y}) "
            f"lên ({end_x}, {end_y}) để tìm [Quẻ lành] "
            f"(lần {swipe_number}/{_MAX_SWIPE_FORTUNE_LOT})."
        )
        try:
            device.shell(
                f"input swipe {start_x} {start_y} {end_x} {end_y} 500"
            )
            time.sleep(0.8)
        except Exception as exc:
            log(f"[{account.username}] Vuốt tìm [Quẻ lành] thất bại: {exc}")
            return steps

        swipe_positions.pop()
        return _run(
            worker, account, steps, device, ocr_client, log, None,
            templates, swipe_positions, fortune_clicked=False,
            buy_try_count=buy_try_count,
        )

    if template_name == _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH:
        if buy_try_count >= _MAX_TRY_BUY_FORTUNE_LOT:
            log(
                f"[{account.username}] Đã thử tìm [Quẻ lành] "
                f"{_MAX_TRY_BUY_FORTUNE_LOT} lần nhưng vẫn ở tab [Shop Chiến Tranh]; "
                "giữ lại step."
            )
            return steps

        next_try = buy_try_count + 1
        log(
            f"[{account.username}] Vẫn đang ở tab [Shop Chiến Tranh]; "
            f"chờ 1 giây rồi thử tìm [Quẻ lành] lần {next_try}/{_MAX_TRY_BUY_FORTUNE_LOT}."
        )
        time.sleep(1.0)
        return _run(
            worker, account, steps, device, ocr_client, log, None,
            templates, swipe_positions, fortune_clicked=fortune_clicked,
            buy_try_count=next_try,
        )

    elif template_name == _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH:
        log(
            f"[{account.username}] Nhận diện hộp thoại [Mua quẻ lành]; "
            "tăng số lượng 10 lần rồi xác nhận."
        )
        try:
            positions = ButtonPositions()
            quantity_x, quantity_y = positions.get(
                "cua_hang.chien_tranh.danh_vong", "tang_so_luong"
            )
            confirm_x, confirm_y = positions.get(
                "cua_hang.chien_tranh.danh_vong", "xac_nhan"
            )

            for index in range(10):
                if not worker._wait_if_paused():
                    log(f"[{account.username}] Dừng tăng số lượng [Quẻ lành] theo yêu cầu.")
                    return steps
                device.shell(f"input tap {quantity_x} {quantity_y}")
                time.sleep(0.15)
                log(
                    f"[{account.username}] Tăng số lượng [Quẻ lành]: "
                    f"{index + 1}/10."
                )

            if not worker._wait_if_paused():
                log(f"[{account.username}] Dừng trước khi xác nhận mua [Quẻ lành].")
                return steps

            device.shell(f"input tap {confirm_x} {confirm_y}")
            log(
                f"[{account.username}] Đã click [Xác nhận] mua [Quẻ lành] "
                f"tại ({confirm_x}, {confirm_y})."
            )
            time.sleep(1.0)
        except Exception as exc:
            log(f"[{account.username}] Thao tác hộp thoại mua [Quẻ lành] thất bại: {exc}")
            return steps

        # Sau khi xác nhận, chụp lại màn hình và nhận diện trạng thái đã mua.
        return _run(
            worker, account, steps, device, ocr_client, log, None,
            templates, swipe_positions, fortune_clicked=False,
        )

    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Tìm và xử lý trạng thái mua Quẻ lành trong Shop Danh Vọng."""
    if _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH not in steps:
        return steps

    log(f"[{account.username}] Bắt đầu [Mua quẻ lành] ...")
    template_names = (
        _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG,
        _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH,
        _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH,
    )
    templates = get_templates(template_names)

    # Hai lượt vuốt từ item2 (dưới) lên item1 (trên).
    swipe_positions = [1] * _MAX_SWIPE_FORTUNE_LOT
    return _run(
        worker, account, steps, device, ocr_client, log, screenshot,
        templates, swipe_positions,
    )
