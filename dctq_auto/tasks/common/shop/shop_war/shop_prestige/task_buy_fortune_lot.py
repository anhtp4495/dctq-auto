"""Nhận diện trạng thái trong tác vụ [Cửa hàng Danh Vọng - Mua quẻ lành]."""

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
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Nhận diện một trong các trạng thái shop; tạm thời ghi log và hoàn tất step."""
    step = _STEP_CUA_HANG_DANH_VONG_MUA_QUE_LANH
    if step not in steps:
        return steps

    if not worker._wait_if_paused():
        log(f"[{account.username}] Nhận diện [Mua quẻ lành] đã dừng theo yêu cầu.")
        return steps

    template_names = (
        _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH,
        _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG,
        _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH,
        _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH,
    )
    templates = get_templates(template_names)

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện [Mua quẻ lành]: {exc}")
        return steps

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

        if template_name == _TEMPLATE_CUA_HANG_DANG_CHON_SHOP_CHIEN_TRANH:
            log(f"[{account.username}] Nhận diện: đang chọn tab [Shop Chiến Tranh].")
        elif template_name == _TEMPLATE_CUA_HANG_DANG_CHON_DANH_VONG:
            log(f"[{account.username}] Nhận diện: đang chọn tab [Shop Danh Vọng].")
        elif template_name == _TEMPLATE_CUA_HANG_CHUA_MUA_QUE_LANH:
            log(f"[{account.username}] Nhận diện: [Quẻ lành] chưa được mua.")
        elif template_name == _TEMPLATE_CUA_HANG_DA_MUA_QUE_LANH:
            log(f"[{account.username}] Nhận diện: [Quẻ lành] đã được mua.")
        elif template_name == _TEMPLATE_CUA_HANG_MAN_HINH_MUA_QUE_LANH:
            log(f"[{account.username}] Nhận diện: hộp thoại [Mua quẻ lành] đang mở.")

        steps.remove(step)
        return steps

    log(f"[{account.username}] Không nhận diện được trạng thái [Mua quẻ lành]; giữ lại step.")
    return steps
