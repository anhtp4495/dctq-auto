"""Điều phối tác vụ đóng góp KNB trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates
from dctq_auto.config.button_positions import ButtonPositions


def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo step đóng góp KNB."""
    if _STEP_QUAN_DOAN_DONG_GOP_KNB not in steps:
        return []

    return [
        _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
        _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
        _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
        _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB,
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB,
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
            return template_name, match
    return None, None


def _tap_match_center(device, match, account, log, label):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm {label} tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def _finish_step(steps, account, log, message):
    """Ghi log và loại step KNB khỏi danh sách chạy."""
    log(f"[{account.username}] {message}")
    if _STEP_QUAN_DOAN_DONG_GOP_KNB in steps:
        steps.remove(_STEP_QUAN_DOAN_DONG_GOP_KNB)
    return steps


# Số lần tối đa xác định game đã tải thành công
_MAX_TRY_DETECT_MAIN_SCREEN = 10

def _run(
    worker, account, steps, device, ocr_client, log, screenshot,
    templates, current_try: int = 1,
) -> list[str]:
    if _STEP_QUAN_DOAN_DONG_GOP_KNB not in steps:
        return steps

    if not worker._wait_if_paused():
        log(f"[{account.username}] Đóng góp KNB tạm dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        return _finish_step(
            steps, account, log,
            f"Không chụp được màn hình đóng góp KNB ({exc}); kết thúc step.",
        )

    template_names = get_template_names(steps)
    template_name, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )

    if template_name is None:
        return _finish_step(
            steps, account, log,
            "Không xác định được trạng thái đóng góp KNB; dừng và bỏ step.",
        )

    if template_name == _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB:
        return _finish_step(
            steps, account, log,
            "Đã nhận diện mức đóng góp 40 KNB; dừng và bỏ step.",
        )

    if template_name in (_TEMPLATE_QUAN_DOAN_DONG_GOP_KNB, _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB, _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB ):
        label = "[Quân đoàn] - Đóng góp KNB"
        _tap_match_center(device, match, account, log, label)
        return _run(
            worker, account, steps, device, ocr_client, log, None,
            templates
        )
        
    if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB:
        tap_x, tap_y = ButtonPositions().get("quan_doan.knb", "dong_man_hinh")
        log(
            f"[{account.username}] Đóng màn hình góp KNB ({tap_x}, {tap_y}); "
        )
        device.shell(f"input tap {tap_x} {tap_y}")

    if current_try < _MAX_TRY_DETECT_MAIN_SCREEN:
        time.sleep(0.7)
        log(f"[{account.username}] [Quân đoàn] Đóng góp KNB chưa xong - Thử lại lần {current_try}.")
        return _run(
            worker, account, steps, device, ocr_client, log, None,
            templates, current_try = current_try + 1
        )

    return _finish_step(
        steps, account, log,
        label,
    )


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Nhận diện và thực hiện các mức đóng góp KNB theo thứ tự."""
    if _STEP_QUAN_DOAN_DONG_GOP_KNB not in steps:
        return steps

    log(f"[{account.username}] Bắt đầu [Đóng góp KNB] ...")
    template_names = get_template_names(steps)
    templates = get_templates(template_names)

    return _run(
        worker, account, steps, device, ocr_client, log, screenshot,
        templates, set(),
    )
