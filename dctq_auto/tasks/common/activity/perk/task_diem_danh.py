"""Tác vụ điểm danh trong nhóm Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_NGAY_CAN_DIEM_DANH,
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_TEMPLATE_NAMES = (
    _TEMPLATE_NGAY_CAN_DIEM_DANH,
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
)


def _find_template(screen_bgr, templates, account, log):
    """Tìm template đầu tiên khớp theo thứ tự ưu tiên."""
    for template_name in _TEMPLATE_NAMES:
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
            return template_name, match
    return None, None


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def _build_day_positions(screen_width: int, screen_height: int) -> list[tuple[int, int, int]]:
    """Tạo tọa độ 31 ô điểm danh theo thứ tự ngày 31 đến ngày 1."""
    grid_left = (484 / 1920) * screen_width
    grid_top = (402 / 1080) * screen_height
    grid_width = ((1822 - 484) / 1920) * screen_width
    grid_height = ((998 - 402) / 1080) * screen_height

    row_ranges = ((1, 9), (10, 18), (19, 27), (28, 31))
    cell_positions = {}
    for row_index, (first_cell, last_cell) in enumerate(row_ranges):
        for cell in range(first_cell, last_cell + 1):
            cell_positions[cell] = (row_index, cell - first_cell)

    positions = []
    for day in range(31, 0, -1):
        row, column = cell_positions[day]
        x = round(grid_left + (column + 0.5) * grid_width / 9)
        y = round(grid_top + (row + 0.5) * grid_height / 4)
        positions.append((day, x, y))
    return positions


def _tap_all_days(worker, device, account, screen_width, screen_height, log) -> bool:
    """Click lần lượt 31 ô điểm danh, từ ngày 31 về ngày 1."""
    day_positions = _build_day_positions(screen_width, screen_height)
    log(f"[{account.username}] Bắt đầu click {len(day_positions)} ô theo thứ tự ngày 31 → ngày 1.")

    for day, x, y in day_positions:
        if not worker._wait_if_paused():
            log(f"[{account.username}] Điểm danh đã dừng theo yêu cầu tại ô ngày {day}.")
            return False
        device.shell(f"input tap {x} {y}")
        log(f"[{account.username}] Đã click ô ngày {day} tại ({x}, {y}).")
        time.sleep(0.15)

    return True


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Xử lý điểm danh bằng template matching và đệ quy sau mỗi lần click."""
    templates = get_templates(_TEMPLATE_NAMES)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Điểm danh đã dừng theo yêu cầu.")
        return False

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện Điểm danh: {exc}")
        return False

    template_name, match = _find_template(screen_bgr, templates, account, log)
    if template_name is None:
        log(f"[{account.username}] Không nhận diện được template Điểm danh; có thể đã chuyển sang màn hình khác.")
        return False

    if template_name == _TEMPLATE_NGAY_CAN_DIEM_DANH:
        try:
            screen_height, screen_width = screen_bgr.shape[:2]
            if not _tap_all_days(
                worker, device, account, screen_width, screen_height, log
            ):
                return False

            # Đóng màn hình lịch điểm danh giống flow cũ.
            close_x = round(0.972396 * screen_width)
            close_y = round(0.119444 * screen_height)
            if not worker._wait_if_paused():
                log(f"[{account.username}] Điểm danh đã dừng trước khi đóng lịch.")
                return False
            log(
                f"[{account.username}] Đóng màn hình lịch điểm danh "
                f"tại ({close_x}, {close_y})."
            )
            device.shell(f"input tap {close_x} {close_y}")
            time.sleep(0.5)
        except Exception as exc:
            log(f"[{account.username}] Không hoàn tất được 31 ô điểm danh: {exc}")
            return False

        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None,
        )

    if template_name == _TEMPLATE_DANG_CHON_DIEM_DANH:
        positions = ButtonPositions()
        for qua_diem_danh_count, button_name in enumerate((
            "qua_diem_danh_10_ngay",
            "qua_diem_danh_20_ngay",
            "qua_diem_danh_30_ngay",
        ), start=1):
            try:
                x, y = positions.get("hoat_dong", button_name)
                log(
                    f"[{account.username}] Nhận mốc quà Điểm danh "
                    f"{qua_diem_danh_count * 10} ngày."
                )
                device.shell(f"input tap {x} {y}")
                time.sleep(0.7)
            except Exception as exc:
                log(f"[{account.username}] Không click được {button_name}: {exc}")
                return False

        log(f"[{account.username}] Điểm danh hoàn tất.")
        return True

    try:
        _tap_match_center(device, match, account, log)
    except Exception as exc:
        log(f"[{account.username}] Không click được template {template_name}: {exc}")
        return False

    return run(
        worker, account, steps, device, ocr_client, log,
        screenshot=None,
    )
