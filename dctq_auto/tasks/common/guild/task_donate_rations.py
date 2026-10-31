"""Điều phối tác vụ đóng góp Lương thảo trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,

    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates
from dctq_auto.config.button_positions import ButtonPositions


def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step đóng góp Lương thảo."""
    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO not in steps:
        return []

    return [
        _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
        _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
        #
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
        _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
        _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH, # fallback
    ]


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template khớp đầu tiên theo thứ tự ưu tiên."""
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
        if match is not None:
            report_template_match(
                log,
                context=f"[{account.username}]",
                template=template,
                match=match,
            )
            return template_name, template, match
    return None, None, None


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Nhận diện và điều hướng vào màn hình đóng góp Lương thảo."""
    selected_steps = {
        step
        for step in (_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,)
        if step in steps
    }
    if not selected_steps:
        return steps

    template_names = get_template_names(steps)
    templates = get_templates(template_names)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Đóng góp Lương thảo đã dừng theo yêu cầu.")
        return steps

    log(f"[{account.username}] Bắt đầu [Đóng góp Lương thảo] ...")
    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình đóng góp Lương thảo: {exc}")
        return steps

    template_name, _, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name is None:
        log(
            f"[{account.username}] Không nhận diện được trạng thái đóng góp "
            "Lương thảo; giữ lại step để thử lại."
        )
        return steps

        
    if template_name == _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB:
        tap_x, tap_y = ButtonPositions().get("quan_doan.luong_thao", "dong_man_hinh")
        log(
            f"[{account.username}] Không đủ tài nguyên - [HỦY] đóng góp tại ({tap_x}, {tap_y}); "
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(1.5)
        device.shell(f"input tap {tap_x} {tap_y}")
        if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in steps:
            steps.remove(_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO:
        if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in steps:
            steps.remove(_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO)
        
        log(f"[{account.username}] Đã xác nhận đóng góp Lương thảo thành công.")
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO:
        _tap_match_center(device, match, account, log)
        return run(worker, account, steps, device, ocr_client, log, screenshot=None)

    if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO:
        log(
            f"[{account.username}] Bắt đầu đóng góp lương thảo ..."
        )
        _tap_match_center(device, match, account, log)
        return run(worker, account, steps, device, ocr_client, log, screenshot=None)
        
    if template_name == _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO:
        log(
            f"[{account.username}] Đang ở màn hình đóng góp lương thảo ..."
        )
        _tap_match_center(device, match, account, log)
        return run(worker, account, steps, device, ocr_client, log, screenshot=None)

    if template_name == _TEMPLATE_QUAN_DOAN_DUNG_NHANH:
        tap_x, tap_y = ButtonPositions().get("quan_doan.luong_thao", "xac_nhan")
        log(
            f"[{account.username}] Dùng nhanh túi lúa tại ({tap_x}, {tap_y}); "
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        return run(worker, account, steps, device, ocr_client, log, screenshot=None)

    log(
        f"[{account.username}] Tiếp tục ..."
    )
    return run(worker, account, steps, device, ocr_client, log, screenshot=None)
