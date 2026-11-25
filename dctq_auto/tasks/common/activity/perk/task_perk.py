"""Điều phối trực tiếp các Poller và thao tác thuộc màn hình Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _STEP_DIEM_DANH,
    _STEP_QUOC_VAN,
    _TEMPLATE_CHUA_CHON_PHUC_LOI,
    _TEMPLATE_DANG_CHON_PHUC_LOI,
    _TEMPLATE_CHUA_CHON_DIEM_DANH,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DIEM_DANH_BU,
    _TEMPLATE_DA_DIEM_DANH,
    _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2,
)
from dctq_auto.tasks.common.activity.perk.polling.daily_check_in_poller import DailyCheckInPoller
from dctq_auto.tasks.common.activity.perk.polling.national_fortune_gift_poller import NationalFortuneGiftPoller
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 6
_TAP_DAY_MAX_TRIES = 3
_PERK_TEMPLATE_NAMES = (
    _TEMPLATE_DANG_CHON_PHUC_LOI,
    _TEMPLATE_CHUA_CHON_PHUC_LOI,
)
_DAILY_TEMPLATE_NAMES = (
    _TEMPLATE_XAC_NHAN_DIEM_DANH_BU,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_DIEM_DANH_BU,
    _TEMPLATE_DA_DIEM_DANH,
)
_SCREEN_TEMPLATE_NAMES = (_TEMPLATE_XAC_NHAN_DIEM_DANH_BU,)
_NATIONAL_FORTUNE_TAB_TEMPLATE_NAMES = (
    _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
)


def pre_perk(steps) -> bool:
    """Chỉ mở Phúc lợi khi có ít nhất một tác vụ con được chọn."""
    return _STEP_DIEM_DANH in steps or _STEP_QUOC_VAN in steps


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.display_name}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def task_open_perk(
    worker, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở màn hình Phúc lợi; đã mở thì xác nhận, chưa mở thì click trung điểm."""
    templates = get_templates(_PERK_TEMPLATE_NAMES)

    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Mở Phúc lợi đã dừng theo yêu cầu.")
            return False

        try:
            current_screenshot = (
                screenshot
                if attempt == 1 and screenshot is not None
                else device.screenshot()
            )
            screen_bgr = cv2.cvtColor(
                np.asarray(current_screenshot), cv2.COLOR_RGB2BGR
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] Không chụp được màn hình khi mở "
                f"Phúc lợi (lần {attempt}/{_MAX_TRIES}): {exc}"
            )
            if attempt < _MAX_TRIES:
                time.sleep(1.0)
                continue
            return False

        matched = False
        for template_name in _PERK_TEMPLATE_NAMES:
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
                log,
                context=f"[{account.display_name}]",
                template=template,
                match=match,
            )
            matched = True

            if template_name == _TEMPLATE_DANG_CHON_PHUC_LOI:
                log(f"[{account.display_name}] Đã xác nhận đang ở màn hình Phúc lợi.")
                return True

            x = (match.left + match.right) // 2
            y = (match.top + match.bottom) // 2
            log(
                f"[{account.display_name}] Phát hiện Phúc lợi chưa được chọn; "
                f"click trung điểm ({x}, {y}) rồi kiểm tra lại."
            )
            try:
                if not worker._wait_if_paused():
                    return False
                device.shell(f"input tap {x} {y}")
            except Exception as exc:
                log(f"[{account.display_name}] Không mở được Phúc lợi: {exc}")
                return False
            time.sleep(0.7)
            break

        if attempt < _MAX_TRIES:
            if not matched:
                log(
                    f"[{account.display_name}] Chưa nhận diện được trạng thái Phúc lợi; "
                    f"thử lại ({attempt + 1}/{_MAX_TRIES})."
                )
            time.sleep(1.0)

    log(f"[{account.display_name}] Mở Phúc lợi thất bại sau {_MAX_TRIES} lần thử.")
    return False

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

def _tap_day(
    worker, device, account, day, region, templates, log
) -> str | None:
    """Click trung điểm vùng ngày; chỉ xác nhận thường khi ô đã điểm danh."""
    tap_x = (region[1] + region[2]) // 2
    tap_y = (region[0] + region[3]) // 2
    already_template = templates.get(_TEMPLATE_DA_DIEM_DANH)
    if already_template is None:
        log(f"[{account.display_name}] Thiếu template đã điểm danh.")
        return None

    for attempt in range(1, _TAP_DAY_MAX_TRIES + 1):
        if not worker._wait_if_paused():
            return None

        log(
            f"[{account.display_name}] Click ngày {day} tại "
            f"({tap_x}, {tap_y}) từ region={region} "
            f"(lần {attempt}/{_TAP_DAY_MAX_TRIES})."
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(0.8)

        try:
            screenshot = device.screenshot()
            screen_bgr = cv2.cvtColor(
                np.asarray(screenshot), cv2.COLOR_RGB2BGR
            )
            screen_template_name, screen_match = _find_template(
                screen_bgr, templates, account, log
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] Không kiểm tra được trạng thái "
                f"sau khi click ngày {day}: {exc}"
            )
            continue

        if screen_template_name == _TEMPLATE_XAC_NHAN_DIEM_DANH_BU:
            log(f"[{account.display_name}] Ngày {day} yêu cầu xác nhận điểm danh bù.")
            if not worker._wait_if_paused():
                return None
            if screen_match is None:
                log(f"[{account.display_name}] Không tìm thấy vùng xác nhận điểm danh bù ngày {day}.")
                return None

            _tap_match_center(device, screen_match, account, log)
            time.sleep(0.8)
            return "catchup"

        try:
            already_match = _match_day_template(
                screen_bgr, already_template, region
            )
        except (ValueError, cv2.error) as exc:
            log(
                f"[{account.display_name}] Lỗi kiểm tra ngày {day} đã điểm danh: {exc}"
            )
            already_match = None

        if already_match is not None:
            report_template_match(
                log,
                context=f"[{account.display_name}] Ngày {day}",
                template=already_template,
                match=already_match,
            )
            return "normal"

        log(
            f"[{account.display_name}] Ngày {day} chưa chuyển sang trạng thái "
            f"đã điểm danh; sẽ thử lại."
        )

    log(
        f"[{account.display_name}] Đã thử click ngày {day} "
        f"{_TAP_DAY_MAX_TRIES} lần nhưng chưa xác nhận được trạng thái đã điểm danh."
    )
    return "normal"

def _scan_day_statuses(
    worker, device, account, screen_width, screen_height, templates, log
):
    """Quét 30 ngày bằng Poller và trả tập ngày đã điểm danh."""
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Điểm danh đã dừng theo yêu cầu.")
        return None, None

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình khi mở Điểm danh: {exc}")
        return None, None

    observation = DailyCheckInPoller().poll(
        screen_bgr,
        screen_width,
        screen_height,
        templates,
        account,
        log,
    )
    if observation is None:
        return None, None

    return observation

def _tap_all_days(
    worker, device, account, screen_width, screen_height, templates, log
) -> bool:
    """Ưu tiên điểm danh ngày kế tiếp, sau đó bù tối đa ba ngày còn thiếu."""
    observation = _scan_day_statuses(
        worker, device, account, screen_width, screen_height, templates, log
    )
    if observation is None:
        return False

    already_days = observation["already_days"]
    region_by_day = dict(observation["day_regions"])
    target_day = observation["target_day"]
    catchup_days = observation["catchup_days"]
    if target_day > 30:
        log(
            f"[{account.display_name}] Không còn ngày điểm danh thường; "
            f"kiểm tra các ngày còn thiếu để điểm danh bù."
        )
    else:
        log(
            f"[{account.display_name}] Ngày cần điểm danh được xác định là "
            f"ngày {target_day}; sẽ ưu tiên xử lý ngày này trước."
        )

    catchup_count = 0
    processed_catchup_days = set()

    # Xử lý ngày kế tiếp trước. Nếu xuất hiện hộp thoại điểm danh bù,
    # ngày đó được tính là một ngày bù và ngày cần điểm danh tăng lên.
    while target_day <= 30:
        if not worker._wait_if_paused():
            return False

        if target_day in already_days:
            target_day += 1
            continue

        region = region_by_day[target_day]
        result = _tap_day(
            worker, device, account, target_day, region, templates, log
        )
        if result is None:
            return False

        if result == "catchup":
            catchup_count += 1
            processed_catchup_days.add(target_day)
            log(
                f"[{account.display_name}] Đã xác nhận ngày {target_day} "
                f"là ngày bù ({catchup_count}/3). Ngày cần điểm danh tiếp theo "
                f"là ngày {target_day + 1}."
            )
            target_day += 1
            continue

        log(f"[{account.display_name}] Đã xử lý ngày cần điểm danh {target_day}.")
        break

    # Sau ngày cần điểm danh, bù các ngày chưa điểm danh nằm trước ngày đó.
    # Tổng số ngày bù, kể cả ngày mục tiêu bất ngờ hiện hộp thoại bù, không quá 3.
    if catchup_count < 3:
        # Poller đã xác định các ô bù. Nếu ngày mục tiêu cũng phát sinh hộp thoại
        # bù, bổ sung các ngày thiếu trước mục tiêu mới theo đúng thứ tự cũ.
        if target_day > observation["target_day"]:
            catchup_days = sorted(set(catchup_days) | {
                day for day in range(1, min(target_day, 31))
                if day not in already_days
            })
        for day in catchup_days:
            if catchup_count >= 3:
                break
            if day in already_days or day in processed_catchup_days:
                continue

            if not worker._wait_if_paused():
                return False

            region = region_by_day[day]
            result = _tap_day(
                worker, device, account, day, region, templates, log
            )
            if result is None:
                return False

            if result == "catchup":
                catchup_count += 1
                processed_catchup_days.add(day)
                log(
                    f"[{account.display_name}] Đã điểm danh bù ngày {day} "
                    f"({catchup_count}/3)."
                )
            else:
                log(
                    f"[{account.display_name}] Ngày {day} không hiện hộp thoại "
                    f"điểm danh bù; đã chuyển về trạng thái màn hình Điểm danh."
                )

    log(
        f"[{account.display_name}] Hoàn tất lượt xử lý: "
        f"1 ngày cần điểm danh và tối đa 3 ngày bù "
        f"(đã bù {catchup_count} ngày)."
    )
    return True

def run_diem_danh(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Xử lý điểm danh sau khi đã mở đúng mục."""
    templates = get_templates(_DAILY_TEMPLATE_NAMES)

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Điểm danh đã dừng theo yêu cầu.")
        return False

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
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

def open_diem_danh(worker, account, device, ocr_client, log, screenshot=None) -> bool:
    """Mở mục Điểm danh; nếu chưa thấy thì vuốt danh sách lên tối đa hai lần."""
    template_names = (
        _TEMPLATE_DANG_CHON_DIEM_DANH,
        _TEMPLATE_CHUA_CHON_DIEM_DANH,
    )
    templates = get_templates(template_names)
    positions = ButtonPositions()

    for attempt in range(6):
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
            continue

        if attempt == 5:
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

def run_le_bao_quoc_van(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Nhận lễ bao Quốc Vận sau khi đã mở đúng mục."""
    poller = NationalFortuneGiftPoller()
    templates = get_templates(poller.TEMPLATE_NAMES)

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Nhận lễ bao Quốc Vận đã dừng theo yêu cầu.")
        return False

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình để nhận diện lễ bao Quốc Vận: {exc}")
        return False

    observation = poller.poll(screen_bgr, templates, account, log)
    template_name = observation["template_name"]
    match = observation["match"]
    if observation["state"] == "not_found":
        log(
            f"[{account.display_name}] Không nhận diện được template lễ bao Quốc Vận; "
            "có thể đã chuyển sang màn hình khác."
        )
        return False

    if template_name == _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI:
        log(f"[{account.display_name}] Đã nhận lễ bao Quốc Vận.")
        return True

    if template_name == _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN:
        tap_x, tap_y = ButtonPositions().get("hoat_dong", "nhan_le_bao_mien_phi")
        device.shell(f"input tap {tap_x} {tap_y}")
        log(f"[{account.display_name}] Nhận lễ bao miễn phí tại ({tap_x}, {tap_y}); ")
        time.sleep(0.7)
        return True

    try:
        _tap_match_center(device, match, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Không click được template {template_name}: {exc}")
        return False

    return run_le_bao_quoc_van(
        worker, account, steps, device, ocr_client, log,
        screenshot=None,
    )

def open_le_bao_quoc_van(worker, account, device, ocr_client, log, screenshot=None) -> bool:
    """Mở mục Lễ bao Quốc Vận; nếu chưa thấy thì vuốt danh sách xuống tối đa hai lần."""
    template_names = (
        _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
        _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
    )
    templates = get_templates(template_names)
    positions = ButtonPositions()

    for attempt in range(6):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Mở Lễ bao Quốc Vận đã dừng theo yêu cầu.")
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
            log(
                f"[{account.display_name}] Không chụp được màn hình khi mở "
                f"Lễ bao Quốc Vận: {exc}"
            )
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
            if template_name == _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN:
                log(f"[{account.display_name}] Đã ở sẵn mục Lễ bao Quốc Vận.")
                return True

            log(f"[{account.display_name}] Phát hiện Lễ bao Quốc Vận chưa được chọn.")
            _tap_match_center(device, match, account, log)
            continue

        if attempt == 5:
            break

        try:
            x1, y1 = positions.get("hoat_dong", "hoat_dong_phuc_loi_item1")
            x2, y2 = positions.get("hoat_dong", "hoat_dong_phuc_loi_item2")
            log(
                f"[{account.display_name}] Chưa thấy Lễ bao Quốc Vận; vuốt từ trên xuống "
                f"lần {attempt + 1}/2: ({x1}, {y1}) -> ({x2}, {y2})."
            )
            device.shell(f"input swipe {x1} {y1} {x2} {y2} 400")
            time.sleep(0.7)
        except Exception as exc:
            log(
                f"[{account.display_name}] Không vuốt được danh sách để tìm "
                f"Lễ bao Quốc Vận: {exc}"
            )
            return False

    log(
        f"[{account.display_name}] Không tìm thấy mục Lễ bao Quốc Vận "
        "sau tối đa 2 lần vuốt."
    )
    return False


def _run_national_fortune_gift(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở mục Quốc Vận, poll trạng thái và thực hiện thao tác nhận lễ bao."""
    if _STEP_QUOC_VAN not in steps:
        return
    if not open_le_bao_quoc_van(worker, account, device, ocr_client, log, screenshot):
        return
    success = run_le_bao_quoc_van(worker, account, steps, device, ocr_client, log)
    if success and _STEP_QUOC_VAN in steps:
        steps.remove(_STEP_QUOC_VAN)


def _run_daily_check_in(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở mục Điểm danh, poll 30 ngày và thực hiện điểm danh."""
    if _STEP_DIEM_DANH not in steps:
        return
    if not open_diem_danh(worker, account, device, ocr_client, log, screenshot):
        return
    success = run_diem_danh(worker, account, steps, device, ocr_client, log)
    if success and _STEP_DIEM_DANH in steps:
        steps.remove(_STEP_DIEM_DANH)


def run_perk(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Điều phối trực tiếp các Poller và quy trình nhận thưởng."""
    if _STEP_QUOC_VAN in steps:
        _run_national_fortune_gift(worker, account, steps, device, ocr_client, log)
    if _STEP_DIEM_DANH in steps:
        _run_daily_check_in(worker, account, steps, device, ocr_client, log)
    return steps


def run(
    worker, account, steps, device, ocr_client, log,
    screenshot=None, swipe_positions=None,
) -> list[str]:
    """Kiểm tra điều kiện, mở Phúc lợi rồi chạy các quy trình con."""
    if not pre_perk(steps):
        return steps
    if not task_open_perk(
        worker, account, device, ocr_client, log, screenshot=screenshot
    ):
        return steps
    return run_perk(worker, account, steps, device, ocr_client, log)
