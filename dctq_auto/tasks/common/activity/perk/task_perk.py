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

def _scan_day_statuses(
    worker, device, account, screen_width, screen_height, templates, log,
    poller=None,
):
    """Gọi Poller và nhận đúng một observation."""
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Điểm danh đã dừng theo yêu cầu.")
        return None

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(
            f"[{account.display_name}] Không chụp được màn hình "
            f"khi kiểm tra Điểm danh: {exc}"
        )
        return None

    poller = poller or DailyCheckInPoller()
    return poller.poll(
        screen_bgr,
        screen_width,
        screen_height,
        templates,
        account,
        log,
    )


def _tap_all_days(
    worker, device, account, screen_width, screen_height, templates, log,
    poller=None,
) -> bool:
    """Điều phối từng observation: xác nhận hoặc xử lý một ô điểm danh."""
    poller = poller or DailyCheckInPoller()
    observation = _scan_day_statuses(
        worker, device, account, screen_width, screen_height, templates, log,
        poller=poller,
    )
    if observation is None:
        return False

    processed_count = 0
    while True:
        if not worker._wait_if_paused():
            return False

        state = observation["state"]
        if state == "completed":
            log(
                f"[{account.display_name}] Hoàn tất xử lý "
                f"{processed_count} ô điểm danh."
            )
            return True

        if state == "confirmation_required":
            log(f"[{account.display_name}] Xác nhận điểm danh bù.")
            _tap_match_center(device, observation["match"], account, log)
            observation = _scan_day_statuses(
                worker, device, account, screen_width, screen_height,
                templates, log, poller=poller,
            )
            if observation is None:
                return False
            continue

        if state != "check_in":
            log(
                f"[{account.display_name}] Poller trả state không hỗ trợ: {state}."
            )
            return False

        day = observation["day"]
        top, left, right, bottom = observation["search_rect"]
        tap_x = (left + right) // 2
        tap_y = (top + bottom) // 2
        log(
            f"[{account.display_name}] Click trung điểm ô ngày {day} "
            f"tại ({tap_x}, {tap_y})."
        )
        try:
            device.shell(f"input tap {tap_x} {tap_y}")
            time.sleep(0.8)
        except Exception as exc:
            log(
                f"[{account.display_name}] Không click được ô ngày "
                f"{day}: {exc}"
            )
            return False

        processed_count += 1
        observation = _scan_day_statuses(
            worker, device, account, screen_width, screen_height,
            templates, log, poller=poller,
        )
        if observation is None:
            return False


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
        poller = DailyCheckInPoller()
        if not _tap_all_days(
            worker, device, account, screen_width, screen_height, templates, log,
            poller=poller,
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

        clicked = False
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
            clicked = True
            break

        if clicked:
            # Sau khi click, chụp màn hình ở vòng lặp kế tiếp để xác nhận.
            # Không vuốt danh sách ngay trong cùng lượt kiểm tra.
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
