"""Thao tác dùng chung để đóng màn hình Hoạt động / Phúc Lợi."""

import json
import time
from pathlib import Path

import cv2
import numpy as np

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


def close_activity(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Đóng Hoạt động bằng Template Matching; nhận screenshot có sẵn nếu được truyền vào."""
    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang đóng màn hình [Hoạt động].")
        return False

    log(f"[{account.username}] Bắt đầu kiểm tra đóng màn hình [Hoạt động].")

    template_names = (
        "main/hoat_dong",
        "hoat_dong/dang_chon_phuc_loi",
        "hoat_dong/dang_chon_hoat_dong",
    )
    templates = get_templates(template_names)

    try:
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
                search_rect=template.search_rect,
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

        if template.id == "hoat_dong":
            log(f"[{account.username}] Đã xác nhận đóng màn hình [Hoạt động] thành công.")
            return True

        if template.id in ("dang_chon_phuc_loi", "dang_chon_hoat_dong"):
            try:
                regions_path = Path(__file__).with_name("regions.json")
                with regions_path.open("r", encoding="utf-8") as file:
                    regions_data = json.load(file)
                elements = regions_data["regions"]["hoat_dong"]["elements"]
                button = next(
                    element for element in elements
                    if element.get("name") == "dong_man_hinh_hoat_dong"
                )
                x = int(button["center"]["x_px"])
                y = int(button["center"]["y_px"])
                log(
                    f"[{account.username}] Màn hình Hoạt động vẫn đang mở "
                    f"({template.id}); click dong_man_hinh_hoat_dong tại ({x}, {y}) "
                    "rồi kiểm tra lại."
                )
                device.shell(f"input tap {x} {y}")
                time.sleep(1.0)
                return close_activity(self, account, device, ocr_client, log)
            except Exception as exc:
                log(f"[{account.username}] Đóng màn hình Hoạt động thất bại: {exc}")
                return False

    log(f"[{account.username}] Không xác định được trạng thái màn hình Hoạt động.")
    return False


def run(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Entry point chuẩn của task; chuyển tiếp tới close_activity."""
    return close_activity(self, account, device, ocr_client, log, screenshot=screenshot)
