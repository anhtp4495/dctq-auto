"""Thao tác dùng chung để mở màn hình Hoạt động."""

import time

import cv2
import numpy as np

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


def open_activity(
    self, account, device, ocr_client, log, screenshot=None
) -> bool:
    """Mở Hoạt động bằng Template Matching; nhận screenshot có sẵn nếu được truyền vào."""
    log(f"[{account.username}] Bắt đầu mở màn hình Hoạt động.")

    template_names = (
        "hoat_dong/dang_chon_man_hinh_hoat_dong",
        "hoat_dong/chua_chon_man_hinh_hoat_dong",
    )
    templates = get_templates(template_names)

    try:
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang mở màn hình Hoạt động.")
            return False
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện Hoạt động: {exc}")
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
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.username}] Lỗi template matching {template_name}: {exc}")
            continue

        if match is None:
            continue

        report_template_match(
            log,
            context=f"[{account.username}]",
            template=template,
            match=match,
        )

        if template.id == "dang_chon_man_hinh_hoat_dong":
            log(f"[{account.username}] Template xác nhận đã ở màn hình Hoạt động.")
            return True

        if template.id == "chua_chon_man_hinh_hoat_dong":
            screen_width, screen_height = screenshot.size
            x = round(0.035937 * screen_width)
            y = round(0.732407 * screen_height)
            log(
                f"[{account.username}] Template xác nhận chưa chọn màn hình Hoạt động; "
                f"click ({x}, {y})."
            )
            try:
                if not self._wait_if_paused():
                    return False
                device.shell(f"input tap {x} {y}")
                time.sleep(3.0)
                if not self._wait_if_paused():
                    return False
                next_screenshot = device.screenshot()
                return open_activity(
                    self, account, device, ocr_client, log,
                    screenshot=next_screenshot,
                )
            except Exception as exc:
                log(f"[{account.username}] Mở màn hình Hoạt động thất bại: {exc}")
                return False

    log(
        f"[{account.username}] Không khớp template "
        "dang_chon_man_hinh_hoat_dong hoặc chua_chon_man_hinh_hoat_dong; "
        "không thực hiện click."
    )
    return False


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới open_activity."""
    return open_activity(
        self, account, device, ocr_client, log, screenshot=screenshot
    )
