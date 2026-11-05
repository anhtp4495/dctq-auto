"""Điều phối các tác vụ thuộc màn hình Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_DIEM_DANH,
    _STEP_QUOC_VAN,
    _TEMPLATE_CHUA_CHON_PHUC_LOI,
    _TEMPLATE_DANG_CHON_PHUC_LOI,
)
from dctq_auto.tasks.common.activity.perk import (
    task_diem_danh,
    task_le_bao_quoc_van,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 6
_TEMPLATE_NAMES = (
    _TEMPLATE_DANG_CHON_PHUC_LOI,
    _TEMPLATE_CHUA_CHON_PHUC_LOI,
)


def pre_perk(steps) -> bool:
    """Chỉ mở Phúc lợi khi có ít nhất một tác vụ con được chọn."""
    return (
        task_diem_danh.pre_diem_danh(steps)
        or task_le_bao_quoc_van.pre_le_bao_quoc_van(steps)
    )


def task_open_perk(
    worker, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở màn hình Phúc lợi; đã mở thì xác nhận, chưa mở thì click trung điểm."""
    templates = get_templates(_TEMPLATE_NAMES)

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


def run_perk(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Điều phối chạy các tác vụ con thuộc Phúc lợi."""
    for step, task, label in (
        (_STEP_QUOC_VAN, task_le_bao_quoc_van, "Lễ bao Quốc Vận"),
        (_STEP_DIEM_DANH, task_diem_danh, "Điểm danh"),
    ):
        task.run(worker, account, steps, device, ocr_client, log)

    return steps

def run(
    worker, account, steps, device, ocr_client, log,
    screenshot=None, swipe_positions=None,
) -> list[str]:
    """Kiểm tra điều kiện, mở Phúc lợi rồi chạy các tác vụ con."""
    if not pre_perk(steps):
        return steps

    if not task_open_perk(
        worker, account, device, ocr_client, log, screenshot=screenshot
    ):
        return steps

    return run_perk(worker, account, steps, device, ocr_client, log)
