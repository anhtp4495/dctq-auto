"""Các hàm dùng chung cho thao tác Giao Tranh."""

import cv2
import numpy as np

from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match


def screen_bgr(device) -> np.ndarray:
    """Chụp màn hình và chuyển ảnh RGB từ ADB sang BGR cho OpenCV."""
    return cv2.cvtColor(np.asarray(device.screenshot()), cv2.COLOR_RGB2BGR)


def match(screen, template, *, account, log):
    """Tìm template và ghi nhận kết quả matching."""
    if template is None:
        return None
    try:
        result = match_template(
            screen,
            template.image,
            threshold=template.threshold,
            method=template.method,
            search_rect=template.search_rect,
            grayscale=template.grayscale,
        )
    except (ValueError, cv2.error) as exc:
        log(f"[{account.username}] Lỗi matching template {template.id}: {exc}")
        return None
    if result is not None:
        report_template_match(
            log, context=f"[{account.username}]", template=template, match=result
        )
    return result


def click_match(device, match_result) -> tuple[int, int]:
    """Click vào trung điểm vùng template khớp."""
    x = round((match_result.left + match_result.right) / 2)
    y = round((match_result.top + match_result.bottom) / 2)
    device.shell(f"input tap {x} {y}")
    return x, y


def tap(
    device,
    point: tuple[int, int],
    *,
    account,
    log,
) -> None:
    """Click vào tọa độ bằng ADB và ghi log lệnh."""
    x, y = point
    command = f"input tap {x} {y}"
    log(f"[{account.username}] ADB: {command}")
    device.shell(command)


def swipe(
    device,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    account,
    log,
    duration_ms: int = 500,
) -> None:
    """Kéo từ tọa độ bắt đầu đến tọa độ kết thúc bằng ADB và ghi log lệnh."""
    x1, y1 = start
    x2, y2 = end
    command = f"input swipe {x1} {y1} {x2} {y2} {duration_ms}"
    log(f"[{account.username}] ADB: {command}")
    device.shell(command)
