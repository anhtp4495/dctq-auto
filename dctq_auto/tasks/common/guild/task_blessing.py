"""Điều phối tác vụ Cầu vận trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


# Số lần tối đa thử nhận diện trạng thái Cầu vận.
_MAX_TRY_DETECT_BLESSING = 10


def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo step Cầu vận."""
    if _STEP_QUAN_DOAN_CAU_VAN not in steps:
        return []

    return [
        _TEMPLATE_QUAN_DOAN_CAU_VAN,
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
        _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN,
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


def _close_blessing_screen(device, account, log):
    """Đóng màn hình Cầu vận theo tọa độ đã cấu hình."""
    tap_x, tap_y = ButtonPositions().get("quan_doan.cau_van", "dong_man_hinh")
    log(
        f"[{account.username}] Đóng màn hình Cầu vận "
        f"theo ButtonPositions tại ({tap_x}, {tap_y})."
    )
    device.shell(f"input tap {tap_x} {tap_y}")
    time.sleep(0.7)


def _finish_step(steps, account, log, message):
    """Ghi log và loại step Cầu vận khỏi danh sách chạy."""
    log(f"[{account.username}] {message}")
    if _STEP_QUAN_DOAN_CAU_VAN in steps:
        steps.remove(_STEP_QUAN_DOAN_CAU_VAN)
    return steps


def _run(
    worker, account, steps, device, ocr_client, log, screenshot,
    templates, try_time: int = 1,
) -> list[str]:
    if _STEP_QUAN_DOAN_CAU_VAN not in steps:
        return steps

    if not worker._wait_if_paused():
        log(f"[{account.username}] Cầu vận tạm dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        if try_time < _MAX_TRY_DETECT_BLESSING:
            log(
                f"[{account.username}] Không chụp được màn hình Cầu vận ({exc}); "
                f"thử lại lần {try_time}/{_MAX_TRY_DETECT_BLESSING}."
            )
            time.sleep(0.7)
            return _run(
                worker, account, steps, device, ocr_client, log, None,
                templates, try_time=try_time + 1,
            )
        return _finish_step(
            steps, account, log,
            f"Không chụp được màn hình Cầu vận sau {_MAX_TRY_DETECT_BLESSING} lần; bỏ step.",
        )

    template_name, match = _find_template(
        screen_bgr, templates, get_template_names(steps), account, log
    )

    if template_name == _TEMPLATE_QUAN_DOAN_CAU_VAN:
        _tap_match_center(device, match, account, log, "Bắt đầu Cầu vận")
    elif template_name == _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN:
        _tap_match_center(device, match, account, log, "nút Cầu vận")
    elif template_name in (
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
    ):
        log(f"[{account.username}] Đã Cầu vận xong.")
        _close_blessing_screen(device, account, log)
        return _finish_step(
            steps, account, log, "Hoàn tất tác vụ Cầu vận Quân đoàn."
        )
    elif template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN:
        _close_blessing_screen(device, account, log)
        return _finish_step(
            steps, account, log, "Đã xử lý màn hình Cầu vận; kết thúc step."
        )
    else:
        if try_time >= _MAX_TRY_DETECT_BLESSING:
            return _finish_step(
                steps, account, log,
                f"Không xác định được trạng thái Cầu vận sau {_MAX_TRY_DETECT_BLESSING} lần; bỏ step.",
            )
        log(
            f"[{account.username}] Chưa xác định được trạng thái Cầu vận; "
            f"thử lại lần {try_time}/{_MAX_TRY_DETECT_BLESSING}."
        )

    if try_time >= _MAX_TRY_DETECT_BLESSING:
        return _finish_step(
            steps, account, log,
            f"Đã thử Cầu vận {_MAX_TRY_DETECT_BLESSING} lần; kết thúc step.",
        )

    return _run(
        worker, account, steps, device, ocr_client, log, None,
        templates, try_time=try_time + 1,
    )


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Nhận diện trạng thái và thực hiện Cầu vận Quân đoàn."""
    if _STEP_QUAN_DOAN_CAU_VAN not in steps:
        return steps

    log(f"[{account.username}] Bắt đầu [Cầu vận Quân đoàn] ...")
    template_names = get_template_names(steps)
    templates = get_templates(template_names)

    return _run(
        worker, account, steps, device, ocr_client, log, screenshot,
        templates,
    )
