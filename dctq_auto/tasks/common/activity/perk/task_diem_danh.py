"""Tác vụ điểm danh trong nhóm Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHUA_CHON_DIEM_DANH,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DIEM_DANH_BU,
    _TEMPLATE_DA_DIEM_DANH,
    _STEP_DIEM_DANH,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_TEMPLATE_NAMES = (
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_DIEM_DANH_BU,
    _TEMPLATE_DA_DIEM_DANH,
)

def pre_diem_danh(steps) -> bool:
    """Cho biết tác vụ Điểm danh có được chọn hay không."""
    return _STEP_DIEM_DANH in steps


_SCREEN_TEMPLATE_NAMES = (
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
)


def _find_template(screen_bgr, templates, account, log):
    """Tìm template đầu tiên khớp theo thứ tự ưu tiên."""
    for template_name in _SCREEN_TEMPLATE_NAMES:
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


def _build_day_regions(screen_width: int, screen_height: int):
    """Tạo vùng tìm kiếm cho 30 ô theo lưới 9 + 9 + 9 + 3."""
    scale_x = screen_width / 1920
    scale_y = screen_height / 1080

    # Tọa độ gốc lấy từ ba ô mẫu: ngày 1, ngày 9 và ngày 30.
    row_bounds = (
        (405, 537),
        (554, 689),
        (704, 841),
        (853, 992),
    )
    row_lengths = (9, 9, 9, 3)
    day_regions = []

    day = 1
    for row_index, (top, bottom) in enumerate(row_bounds):
        for column in range(row_lengths[row_index]):
            left = round((480 + column * 150) * scale_x)
            right = round((620 + column * 150) * scale_x)
            region = (
                round(top * scale_y),
                left,
                right,
                round(bottom * scale_y),
            )
            center_x = (left + right) // 2
            center_y = (region[0] + region[3]) // 2
            day_regions.append((day, region, center_x, center_y))
            day += 1

    return day_regions


def _match_day_template(screen_bgr, template, search_rect):
    """Tìm template trạng thái trong đúng vùng của một ngày."""
    return match_template(
        screen_bgr,
        template.image,
        threshold=template.threshold,
        method=template.method,
        search_rect=search_rect,
        grayscale=template.grayscale,
    )

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
    """Nhận diện trạng thái rồi chỉ click các ngày chưa điểm danh."""
    day_regions = _build_day_regions(screen_width, screen_height)
    already_template = templates.get(_TEMPLATE_DA_DIEM_DANH)
    catchup_template = templates.get(_TEMPLATE_DIEM_DANH_BU)

    if already_template is None or catchup_template is None:
        log(f"[{account.display_name}] Thiếu template trạng thái ngày điểm danh.")
        return False

    log(f"[{account.display_name}] Bắt đầu kiểm tra {len(day_regions)} ngày điểm danh.")

    for day, search_rect, x, y in day_regions:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Điểm danh đã dừng theo yêu cầu tại ngày {day}.")
            return False

        try:
            screenshot = device.screenshot()
            screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)

            already_match = _match_day_template(
                screen_bgr, already_template, search_rect
            )
            if already_match is not None:
                log(f"[{account.display_name}] Ngày {day} đã điểm danh; bỏ qua.")
                continue

            catchup_match = _match_day_template(
                screen_bgr, catchup_template, search_rect
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.display_name}] Lỗi nhận diện trạng thái ngày {day}: {exc}")
            return False
        except Exception as exc:
            log(f"[{account.display_name}] Không kiểm tra được ngày {day}: {exc}")
            return False

        if not worker._wait_if_paused():
            return False

        if catchup_match is not None:
            report_template_match(
                log,
                context=f"[{account.display_name}] Ngày {day}",
                template=catchup_template,
                match=catchup_match,
            )
            log(f"[{account.display_name}] Ngày {day} là ngày điểm danh bù; click ({x}, {y}).")
            device.shell(f"input tap {x} {y}")
            time.sleep(1.0)

            if not _tap_confirmation_if_visible(
                worker, device, account, templates, log
            ):
                log(f"[{account.display_name}] Không xử lý được xác nhận điểm danh bù ngày {day}.")
                return False
            continue

        log(f"[{account.display_name}] Ngày {day} chưa điểm danh; click ({x}, {y}).")
        device.shell(f"input tap {x} {y}")
        time.sleep(0.15)

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
