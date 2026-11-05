"""Tác vụ điểm danh trong nhóm Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHUA_CHON_DIEM_DANH,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_TEMPLATE_NAMES = (
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
)


def _find_template(screen_bgr, templates, account, log):
    """Tìm template đầu tiên khớp theo thứ tự ưu tiên."""
    for template_name in _TEMPLATE_NAMES:
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


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.display_name}] Click trung điểm template tại ({x}, {y}).")
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


def _tap_confirmation_if_visible(worker, device, account, templates, log) -> bool:
    """Kiểm tra và click xác nhận điểm danh bù nếu hộp thoại xuất hiện."""
    if not worker._wait_if_paused():
        return False

    template = templates.get(_TEMPLATE_XAC_NHAN_DIEM_DANH_BU)
    if template is None:
        log(
            f"[{account.display_name}] Không tải được template "
            f"{_TEMPLATE_XAC_NHAN_DIEM_DANH_BU}; bỏ qua kiểm tra xác nhận."
        )
        return True

    screenshot = device.screenshot()
    screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
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
        log(
            f"[{account.display_name}] Lỗi nhận diện xác nhận điểm danh bù: {exc}"
        )
        return True

    if match is None:
        return True

    report_template_match(
        log,
        context=f"[{account.display_name}]",
        template=template,
        match=match,
    )
    if not worker._wait_if_paused():
        return False

    log(f"[{account.display_name}] Phát hiện hộp thoại xác nhận điểm danh bù.")
    _tap_match_center(device, match, account, log)
    return True


def _tap_all_days(
    worker, device, account, screen_width, screen_height, templates, log
) -> bool:
    """Click lần lượt 31 ô điểm danh, xử lý xác nhận điểm danh bù nếu xuất hiện."""
    day_positions = _build_day_positions(screen_width, screen_height)
    log(f"[{account.display_name}] Bắt đầu click {len(day_positions)} ô theo thứ tự ngày 31 → ngày 1.")

    for day, x, y in day_positions:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Điểm danh đã dừng theo yêu cầu tại ô ngày {day}.")
            return False
        device.shell(f"input tap {x} {y}")
        log(f"[{account.display_name}] Đã click ô ngày {day} tại ({x}, {y}).")
        time.sleep(0.15)

        if not _tap_confirmation_if_visible(
            worker, device, account, templates, log
        ):
            log(
                f"[{account.display_name}] Điểm danh đã dừng khi xử lý xác nhận "
                f"tại ô ngày {day}."
            )
            return False

    return True


def run_diem_danh(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Xử lý điểm danh sau khi đã mở đúng mục."""
    templates = get_templates(_TEMPLATE_NAMES)

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Điểm danh đã dừng theo yêu cầu.")
        return False

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình để nhận diện Điểm danh: {exc}")
        return False

    template_name, match = _find_template(screen_bgr, templates, account, log)
    if template_name is None:
        log(f"[{account.display_name}] Không nhận diện được template Điểm danh; có thể đã chuyển sang màn hình khác.")
        return False

    if template_name == _TEMPLATE_DANG_CHON_DIEM_DANH:
        try:
            screen_height, screen_width = screen_bgr.shape[:2]
            if not _tap_all_days(
                worker, device, account, screen_width, screen_height, templates, log
            ):
                return False

        except Exception as exc:
            log(f"[{account.display_name}] Không hoàn tất được 31 ô điểm danh: {exc}")
            return False

        positions = ButtonPositions()
        for qua_diem_danh_count, button_name in enumerate((
            "qua_diem_danh_10_ngay",
            "qua_diem_danh_20_ngay",
            "qua_diem_danh_30_ngay",
        ), start=1):
            try:
                x, y = positions.get("hoat_dong", button_name)
                log(
                    f"[{account.display_name}] Nhận mốc quà Điểm danh "
                    f"{qua_diem_danh_count * 10} ngày."
                )
                device.shell(f"input tap {x} {y}")
                time.sleep(0.7)
            except Exception as exc:
                log(f"[{account.display_name}] Không click được {button_name}: {exc}")
                return False

        log(f"[{account.display_name}] Điểm danh hoàn tất.")
        return True

    try:
        _tap_match_center(device, match, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Không click được template {template_name}: {exc}")
        return False

    return run_diem_danh(
        worker, account, steps, device, ocr_client, log,
        screenshot=None,
    )


def open_diem_danh(worker, account, device, ocr_client, log, screenshot=None) -> bool:
    """Mở mục Điểm danh; nếu chưa thấy thì vuốt danh sách lên tối đa hai lần."""
    template_names = (
        _TEMPLATE_DANG_CHON_DIEM_DANH,
        _TEMPLATE_CHUA_CHON_DIEM_DANH,
    )
    templates = get_templates(template_names)
    positions = ButtonPositions()

    for attempt in range(3):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Mở Điểm danh đã dừng theo yêu cầu.")
            return False

        try:
            current_screenshot = (
                screenshot if attempt == 0 and screenshot is not None
                else device.screenshot()
            )
            screen_bgr = cv2.cvtColor(
                np.asarray(current_screenshot), cv2.COLOR_RGB2BGR
            )
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình khi mở Điểm danh: {exc}")
            return False

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
                log(f"[{account.display_name}] Lỗi nhận diện {template_name}: {exc}")
                continue
            if match is None:
                continue

            report_template_match(
                log, context=f"[{account.display_name}]", template=template, match=match
            )
            if template_name == _TEMPLATE_DANG_CHON_DIEM_DANH:
                log(f"[{account.display_name}] Đã ở sẵn mục Điểm danh.")
                return True

            log(f"[{account.display_name}] Phát hiện Điểm danh chưa được chọn.")
            _tap_match_center(device, match, account, log)
            return True

        if attempt == 2:
            break

        try:
            x1, y1 = positions.get("hoat_dong", "hoat_dong_phuc_loi_item2")
            x2, y2 = positions.get("hoat_dong", "hoat_dong_phuc_loi_item1")
            log(
                f"[{account.display_name}] Chưa thấy Điểm danh; vuốt từ dưới lên "
                f"lần {attempt + 1}/2: ({x1}, {y1}) -> ({x2}, {y2})."
            )
            device.shell(f"input swipe {x1} {y1} {x2} {y2} 400")
            time.sleep(0.7)
        except Exception as exc:
            log(f"[{account.display_name}] Không vuốt được danh sách để tìm Điểm danh: {exc}")
            return False

    log(f"[{account.display_name}] Không tìm thấy mục Điểm danh sau tối đa 2 lần vuốt.")
    return False


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Mở mục Điểm danh trước, sau đó chạy quy trình điểm danh."""
    if not open_diem_danh(
        worker, account, device, ocr_client, log, screenshot=screenshot
    ):
        return False
    return run_diem_danh(
        worker, account, steps, device, ocr_client, log, screenshot=None
    )
