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
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 10
_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN,
)
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
    _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN,
)
_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)


def pre_blessing(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ Cầu vận hay không."""
    if _STEP_QUAN_DOAN_CAU_VAN not in steps:
        log("Cầu vận Quân đoàn: không có step trong danh sách; bỏ qua.")
        return False

    log("Cầu vận Quân đoàn: tìm thấy step; bắt đầu thực hiện.")
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


def open_blessing(worker, account, device, log, screenshot=None) -> bool:
    """Mở màn hình Cầu vận và chỉ thành công khi xác nhận được màn hình đích."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình Cầu vận Quân đoàn.")
    templates = get_templates(_OPEN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang mở màn hình Cầu vận.")
            return False

        if current_try == 1 and screenshot is not None:
            try:
                screen_bgr = cv2.cvtColor(
                    np.asarray(screenshot), cv2.COLOR_RGB2BGR
                )
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không xử lý được screenshot khi mở Cầu vận: {exc}"
                )
                return False
        else:
            screen_bgr = _capture_screen(device, account, log, "khi mở Cầu vận")
            if screen_bgr is None:
                return False

        template_name, match = _find_template(
            screen_bgr,
            templates,
            (_TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN, _TEMPLATE_QUAN_DOAN_CAU_VAN),
            account,
            log,
        )

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN:
            log(f"[{account.display_name}] Đã xác nhận mở màn hình Cầu vận.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_CAU_VAN:
            if not _tap_match_center(device, match, account, log, "lối vào Cầu vận"):
                return False
            log(f"[{account.display_name}] Đã chọn Cầu vận; chờ xác nhận màn hình đích.")
            time.sleep(0.8)
            continue

        log(
            f"[{account.display_name}] Chưa nhận diện được màn hình Cầu vận "
            f"(lần {current_try}/{_MAX_TRIES})."
        )
        time.sleep(0.8)

    log(f"[{account.display_name}] Mở màn hình Cầu vận thất bại sau {_MAX_TRIES} lần thử.")
    return False


def run_blessing(worker, account, device, log) -> bool:
    """Thực hiện Cầu vận; chỉ trả về True khi xác nhận trạng thái hết lượt."""
    templates = get_templates(_RUN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Cầu vận đã dừng theo yêu cầu.")
            return False

        screen_bgr = _capture_screen(device, account, log, "Cầu vận")
        if screen_bgr is None:
            return False

        template_name, match = _find_template(
            screen_bgr, templates, _RUN_TEMPLATES, account, log
        )

        if template_name in (
            _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
            _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
        ):
            log(f"[{account.display_name}] Đã xác nhận Cầu vận hết lượt.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN:
            if not _tap_match_center(device, match, account, log, "nút Cầu vận"):
                return False
            time.sleep(0.8)
            continue

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN:
            log(
                f"[{account.display_name}] Đang ở màn hình Cầu vận nhưng chưa nhận diện "
                f"được trạng thái thao tác (lần {current_try}/{_MAX_TRIES})."
            )
        else:
            log(
                f"[{account.display_name}] Không nhận diện được trạng thái Cầu vận "
                f"(lần {current_try}/{_MAX_TRIES})."
            )

        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không xác nhận được Cầu vận hoàn tất "
        f"sau {_MAX_TRIES} lần thử; giữ nguyên step."
    )
    return False


def close_blessing(worker, account, device, log) -> bool:
    """Đóng màn hình Cầu vận và xác nhận đã trở về giao diện Quân đoàn."""
    templates = get_templates(_CLOSE_TEMPLATES)

    for current_try in range(1, 3):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đóng màn hình Cầu vận.")
            return False

        screen_bgr = _capture_screen(device, account, log, "khi đóng Cầu vận")
        if screen_bgr is None:
            return False

        template_name, _ = _find_template(
            screen_bgr, templates, _CLOSE_TEMPLATES, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN:
            tap_x, tap_y = ButtonPositions().get(
                "quan_doan.cau_van", "dong_man_hinh"
            )
            device.shell(f"input tap {tap_x} {tap_y}")
            log(f"[{account.display_name}] Đóng màn hình Cầu vận tại ({tap_x}, {tap_y}); Chờ xác nhận")
        elif template_name in (_TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH, _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,):
            log(f"[{account.display_name}] Màn hình cầu vận đã đóng; ")
            return True
        elif template_name in (_TEMPLATE_QUAN_DOAN_CAU_VAN, _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,):
            log(f"[{account.display_name}] Màn hình cầu vận đã đóng; ")
            return True

        time.sleep(1)

    log(
        f"[{account.display_name}] Không xác nhận được đã đóng màn hình Cầu vận "
        f"sau {_MAX_TRIES} lần thử."
    )
    return False


def post_blessing(steps, account, log) -> list[str]:
    """Loại step Cầu vận sau khi đã hoàn tất và đóng màn hình thành công."""
    if _STEP_QUAN_DOAN_CAU_VAN in steps:
        steps.remove(_STEP_QUAN_DOAN_CAU_VAN)
    log(f"[{account.display_name}] Hoàn tất tác vụ Cầu vận Quân đoàn.")
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Điều phối đầy đủ quy trình Cầu vận: pre, open, run, close và post."""
    if not pre_blessing(steps, log):
        return steps

    log(f"[{account.display_name}] Bắt đầu quy trình Cầu vận Quân đoàn.")

    try:
        if not open_blessing(worker, account, device, log, screenshot=screenshot):
            log(f"[{account.display_name}] Không mở được Cầu vận; giữ nguyên step.")
            return steps

        if not run_blessing(worker, account, device, log):
            return steps

        if not close_blessing(worker, account, device, log):
            log(f"[{account.display_name}] Chưa đóng được Cầu vận; giữ nguyên step.")
            return steps

        return post_blessing(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình Cầu vận phát sinh lỗi: {exc}")
        return steps
