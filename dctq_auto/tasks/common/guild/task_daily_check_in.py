"""Điều phối tác vụ báo danh hằng ngày trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 10
_OPEN_TEMPLATES = (_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,)
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
_CLOSE_TEMPLATES = (_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,)


def pre_daily_check_in(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ báo danh Quân đoàn hay không."""
    if _STEP_QUAN_DOAN_BAO_DANH not in steps:
        log("Báo danh Quân đoàn: không có step trong danh sách; bỏ qua.")
        return False

    log("Báo danh Quân đoàn: tìm thấy step; bắt đầu thực hiện.")
    return True


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template và vị trí khớp đầu tiên theo thứ tự ưu tiên."""
    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            log(f"[{account.display_name}] Không tải được template {template_name}; bỏ qua.")
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
            log(f"[{account.display_name}] Lỗi template matching {template_name}: {exc}")
            continue

        if match is not None:
            report_template_match(
                log,
                context=f"[{account.display_name}]",
                template=template,
                match=match,
            )
            return template_name, match

    return None, None


def _capture_screen(device, account, log, action: str):
    """Chụp màn hình và chuyển sang BGR; lỗi được trả về cho caller xử lý."""
    try:
        screenshot = device.screenshot()
        return cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình {action}: {exc}")
        return None


def _tap_match_center(device, match, account, log, label: str) -> bool:
    """Click trung điểm template; không tiếp tục nếu thao tác ADB lỗi."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    try:
        device.shell(f"input tap {x} {y}")
    except Exception as exc:
        log(f"[{account.display_name}] Không click được {label} tại ({x}, {y}): {exc}")
        return False

    log(f"[{account.display_name}] Click trung điểm {label} tại ({x}, {y}).")
    return True


def _tap_check_in_button(device, account, log) -> bool:
    """Click nút báo danh theo tọa độ cấu hình."""
    try:
        x, y = ButtonPositions().get("quan_doan", "bao_danh")
        device.shell(f"input tap {x} {y}")
    except Exception as exc:
        log(f"[{account.display_name}] Không click được nút báo danh Quân đoàn: {exc}")
        return False

    log(f"[{account.display_name}] Click nút báo danh Quân đoàn tại ({x}, {y}).")
    return True


def open_daily_check_in(worker, account, device, log, screenshot=None) -> bool:
    """Xác nhận đang ở màn hình chính Quân đoàn trước khi báo danh."""
    templates = get_templates(_OPEN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi mở màn hình báo danh Quân đoàn.")
            return False

        if current_try == 1 and screenshot is not None:
            try:
                screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
            except Exception as exc:
                log(f"[{account.display_name}] Không xử lý được screenshot khi mở báo danh: {exc}")
                return False
        else:
            screen_bgr = _capture_screen(device, account, log, "khi mở báo danh Quân đoàn")
            if screen_bgr is None:
                return False

        template_name, _ = _find_template(
            screen_bgr, templates, _OPEN_TEMPLATES, account, log
        )
        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            log(f"[{account.display_name}] Đã xác nhận màn hình chính Quân đoàn.")
            return True

        log(
            f"[{account.display_name}] Chưa nhận diện được màn hình chính Quân đoàn "
            f"(lần {current_try}/{_MAX_TRIES})."
        )
        time.sleep(0.8)

    log(f"[{account.display_name}] Không xác nhận được màn hình Quân đoàn.")
    return False


def run_daily_check_in(worker, account, device, log) -> bool:
    """Báo danh và chỉ thành công khi nhận diện được trạng thái đã báo danh."""
    templates = get_templates(_RUN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Báo danh Quân đoàn đã dừng theo yêu cầu.")
            return False

        screen_bgr = _capture_screen(device, account, log, "báo danh Quân đoàn")
        if screen_bgr is None:
            return False

        template_name, match = _find_template(
            screen_bgr, templates, _RUN_TEMPLATES, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_DA_BAO_DANH:
            log(f"[{account.display_name}] Đã xác nhận báo danh Quân đoàn.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH:
            if not _tap_match_center(
                device, match, account, log, "trạng thái chưa báo danh"
            ):
                return False
        elif template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            if not _tap_check_in_button(device, account, log):
                return False
        else:
            log(
                f"[{account.display_name}] Không nhận diện được trạng thái báo danh "
                f"(lần {current_try}/{_MAX_TRIES})."
            )

        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không xác nhận được báo danh hoàn tất "
        f"sau {_MAX_TRIES} lần thử; giữ nguyên step."
    )
    return False


def close_daily_check_in(worker, account, device, log) -> bool:
    """Xác nhận đã trở về màn hình chính Quân đoàn sau khi báo danh."""
    templates = get_templates(_CLOSE_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi xác nhận màn hình Quân đoàn.")
            return False

        screen_bgr = _capture_screen(device, account, log, "khi xác nhận màn hình Quân đoàn")
        if screen_bgr is None:
            return False

        template_name, _ = _find_template(
            screen_bgr, templates, _CLOSE_TEMPLATES, account, log
        )
        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            log(f"[{account.display_name}] Đã xác nhận đang ở màn hình chính Quân đoàn.")
            return True

        log(
            f"[{account.display_name}] Chưa xác nhận được màn hình chính Quân đoàn "
            f"(lần {current_try}/{_MAX_TRIES})."
        )
        time.sleep(0.8)

    log(f"[{account.display_name}] Không xác nhận được màn hình chính Quân đoàn.")
    return False


def post_daily_check_in(steps, account, log) -> list[str]:
    """Loại step báo danh sau khi đã xác nhận hoàn tất."""
    if _STEP_QUAN_DOAN_BAO_DANH in steps:
        steps.remove(_STEP_QUAN_DOAN_BAO_DANH)
    log(f"[{account.display_name}] Hoàn tất tác vụ báo danh Quân đoàn.")
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Điều phối đầy đủ quy trình báo danh: pre, open, run, close và post."""
    if not pre_daily_check_in(steps, log):
        return steps

    log(f"[{account.display_name}] Bắt đầu quy trình báo danh Quân đoàn.")

    try:
        if not open_daily_check_in(
            worker, account, device, log, screenshot=screenshot
        ):
            log(f"[{account.display_name}] Không mở được màn hình Quân đoàn; giữ nguyên step.")
            return steps

        if not run_daily_check_in(worker, account, device, log):
            return steps

        if not close_daily_check_in(worker, account, device, log):
            log(f"[{account.display_name}] Chưa xác nhận được màn hình Quân đoàn; giữ nguyên step.")
            return steps

        return post_daily_check_in(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình báo danh Quân đoàn phát sinh lỗi: {exc}")
        return steps
