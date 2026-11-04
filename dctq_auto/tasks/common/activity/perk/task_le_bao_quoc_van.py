"""Tác vụ nhận lễ bao Quốc Vận trong nhóm Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2,
)

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_TEMPLATE_NAMES = (
    _TEMPLATE_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI1,
    _TEMPLATE_TAT_THONG_BAO_NHAN_LE_BAO_MIEN_PHI2,
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


def _run_le_bao_quoc_van(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Nhận lễ bao Quốc Vận sau khi đã mở đúng mục."""
    templates = get_templates(_TEMPLATE_NAMES)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Nhận lễ bao Quốc Vận đã dừng theo yêu cầu.")
        return False

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện lễ bao Quốc Vận: {exc}")
        return False

    template_name, match = _find_template(screen_bgr, templates, account, log)
    if template_name is None:
        log(
            f"[{account.username}] Không nhận diện được template lễ bao Quốc Vận; "
            "có thể đã chuyển sang màn hình khác."
        )
        return False

    if template_name == _TEMPLATE_DA_NHAN_LE_BAO_MIEN_PHI:
        log(f"[{account.username}] Đã nhận lễ bao Quốc Vận.")
        return True

    try:
        _tap_match_center(device, match, account, log)
    except Exception as exc:
        log(f"[{account.username}] Không click được template {template_name}: {exc}")
        return False

    return _run_le_bao_quoc_van(
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

    for attempt in range(3):
        if not worker._wait_if_paused():
            log(f"[{account.username}] Mở Lễ bao Quốc Vận đã dừng theo yêu cầu.")
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
                f"[{account.username}] Không chụp được màn hình khi mở "
                f"Lễ bao Quốc Vận: {exc}"
            )
            return False

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
                    grayscale=template.grayscale,
                )
            except (ValueError, cv2.error) as exc:
                log(f"[{account.username}] Lỗi nhận diện {template_name}: {exc}")
                continue
            if match is None:
                continue

            report_template_match(
                log, context=f"[{account.username}]", template=template, match=match
            )
            if template_name == _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN:
                log(f"[{account.username}] Đã ở sẵn mục Lễ bao Quốc Vận.")
                return True

            log(f"[{account.username}] Phát hiện Lễ bao Quốc Vận chưa được chọn.")
            _tap_match_center(device, match, account, log)
            return True

        if attempt == 2:
            break

        try:
            x1, y1 = positions.get("hoat_dong", "hoat_dong_phuc_loi_item1")
            x2, y2 = positions.get("hoat_dong", "hoat_dong_phuc_loi_item2")
            log(
                f"[{account.username}] Chưa thấy Lễ bao Quốc Vận; vuốt từ trên xuống "
                f"lần {attempt + 1}/2: ({x1}, {y1}) -> ({x2}, {y2})."
            )
            device.shell(f"input swipe {x1} {y1} {x2} {y2} 400")
            time.sleep(0.7)
        except Exception as exc:
            log(
                f"[{account.username}] Không vuốt được danh sách để tìm "
                f"Lễ bao Quốc Vận: {exc}"
            )
            return False

    log(
        f"[{account.username}] Không tìm thấy mục Lễ bao Quốc Vận "
        "sau tối đa 2 lần vuốt."
    )
    return False


def run_le_bao_quoc_van(
    worker, account, steps, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở mục Lễ bao Quốc Vận trước, sau đó thực hiện quy trình nhận lễ bao."""
    if not open_le_bao_quoc_van(
        worker, account, device, ocr_client, log, screenshot=screenshot
    ):
        return False
    return _run_le_bao_quoc_van(
        worker, account, steps, device, ocr_client, log, screenshot=None
    )


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point tương thích với bộ điều phối task."""
    return run_le_bao_quoc_van(
        worker, account, steps, device, ocr_client, log, screenshot=screenshot
    )
