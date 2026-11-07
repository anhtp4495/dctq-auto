"""Điều phối tác vụ đóng góp KNB trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 10
_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB,
)
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB,
)
_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
)


def pre_knb(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ đóng góp KNB hay không."""
    if _STEP_QUAN_DOAN_DONG_GOP_KNB not in steps:
        log("Đóng góp KNB: không có step trong danh sách; bỏ qua.")
        return False

    log("Đóng góp KNB: tìm thấy step; bắt đầu thực hiện.")
    return True


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template và vị trí khớp đầu tiên theo thứ tự ưu tiên."""
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


def _capture_screen(device, account, log, action: str):
    """Chụp màn hình và chuyển sang BGR; lỗi được trả về cho caller xử lý."""
    try:
        screenshot = device.screenshot()
        return cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình {action}: {exc}")
        return None


def _tap_match_center(device, match, account, log, label: str) -> bool:
    """Click trung điểm template; không tiếp tục nếu thao tác ADB lỗi."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    try:
        device.shell(f"input tap {x} {y}")
    except Exception as exc:
        log(f"[{account.display_name}] Không click được {label} tại ({x}, {y}): {exc}")
        return False

    log(f"[{account.display_name}] Click trung điểm {label} tại ({x}, {y}).")
    return True


def _tap_close_button(device, account, log) -> bool:
    """Đóng giao diện đóng góp KNB theo tọa độ cấu hình."""
    try:
        x, y = ButtonPositions().get("quan_doan.knb", "dong_man_hinh")
        device.shell(f"input tap {x} {y}")
    except Exception as exc:
        log(f"[{account.display_name}] Không đóng được màn hình góp KNB: {exc}")
        return False

    log(f"[{account.display_name}] Đóng màn hình góp KNB tại ({x}, {y}).")
    return True


def open_knb(worker, account, device, log, screenshot=None) -> bool:
    """Mở giao diện đóng góp KNB và xác nhận được trạng thái đích."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình đóng góp KNB.")
    templates = get_templates(_OPEN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi mở màn hình đóng góp KNB.")
            return False

        if current_try == 1 and screenshot is not None:
            try:
                screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
            except Exception as exc:
                log(f"[{account.display_name}] Không xử lý được screenshot khi mở KNB: {exc}")
                return False
        else:
            screen_bgr = _capture_screen(device, account, log, "khi mở đóng góp KNB")
            if screen_bgr is None:
                return False

        template_name, match = _find_template(
            screen_bgr, templates, _OPEN_TEMPLATES, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB:
            if not _tap_match_center(device, match, account, log, "nút đóng góp KNB"):
                return False
            time.sleep(0.8)
            continue

        if template_name in _OPEN_TEMPLATES[1:]:
            log(f"[{account.display_name}] Đã nhận diện được giao diện đóng góp KNB.")
            return True

        log(
            f"[{account.display_name}] Chưa nhận diện được giao diện đóng góp KNB "
            f"(lần {current_try}/{_MAX_TRIES})."
        )
        time.sleep(0.8)

    log(f"[{account.display_name}] Không mở được giao diện đóng góp KNB.")
    return False


def run_knb(worker, account, device, log, skipped_templates=None) -> bool:
    """Thực hiện lần lượt các mức đóng góp; chỉ thành công khi xác nhận trạng thái kết thúc."""
    templates = get_templates(_RUN_TEMPLATES)
    if skipped_templates is None:
        skipped_templates = set()

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đóng góp KNB đã dừng theo yêu cầu.")
            return False

        screen_bgr = _capture_screen(device, account, log, "đóng góp KNB")
        if screen_bgr is None:
            return False

        template_names = tuple(
            name for name in _RUN_TEMPLATES if name not in skipped_templates
        )
        template_name, match = _find_template(
            screen_bgr, templates, template_names, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB:
            log(f"[{account.display_name}] Không đủ điều kiện đóng góp KNB.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB:
            if not _tap_close_button(device, account, log):
                return False
            log(f"[{account.display_name}] Đã nhận diện mức đóng góp 40 KNB.")
            return True

        if template_name in (
            _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
            _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
        ):
            if not _tap_match_center(
                device, match, account, log, f"mức đóng góp {template_name}"
            ):
                return False
            skipped_templates.add(template_name)
            time.sleep(0.8)
            continue

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB:
            if not _tap_close_button(device, account, log):
                return False
            log(f"[{account.display_name}] Đã xử lý xong giao diện đóng góp KNB.")
            return True

        log(
            f"[{account.display_name}] Không nhận diện được trạng thái đóng góp KNB "
            f"(lần {current_try}/{_MAX_TRIES})."
        )
        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không xác nhận được hoàn tất đóng góp KNB "
        f"sau {_MAX_TRIES} lần thử; giữ nguyên step."
    )
    return False


def close_knb(worker, account, device, log, skipped_templates=None) -> bool:
    """Xác nhận đã đóng giao diện KNB và trở về màn hình chính Quân đoàn."""
    skipped_templates = skipped_templates or set()
    close_templates = (*_CLOSE_TEMPLATES, *skipped_templates)
    templates = get_templates(close_templates)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi xác nhận đóng màn hình KNB.")
            return False

        screen_bgr = _capture_screen(device, account, log, "khi đóng giao diện KNB")
        if screen_bgr is None:
            return False

        template_name, _ = _find_template(
            screen_bgr, templates, close_templates, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            log(f"[{account.display_name}] Đã xác nhận trở về màn hình chính Quân đoàn.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB:
            # Giữ nguyên hành vi cũ: thông báo không đủ điều kiện là trạng thái kết thúc,
            # không thực hiện thao tác đóng popup.
            log(f"[{account.display_name}] Kết thúc do không đủ điều kiện đóng góp KNB.")
            return True

        if template_name in skipped_templates:
            log(
                f"[{account.display_name}] Template {template_name} đã được xử lý trước đó; "
                "xem như đã hoàn tất đóng góp KNB."
            )
            return True

        log(
            f"[{account.display_name}] Chưa xác nhận được màn hình chính Quân đoàn "
            f"(lần {current_try}/{_MAX_TRIES})."
        )
        time.sleep(0.8)

    log(f"[{account.display_name}] Không xác nhận được đã đóng giao diện KNB.")
    return False


def post_knb(steps, account, log) -> list[str]:
    """Loại step KNB sau khi đã hoàn tất quy trình."""
    if _STEP_QUAN_DOAN_DONG_GOP_KNB in steps:
        steps.remove(_STEP_QUAN_DOAN_DONG_GOP_KNB)
    log(f"[{account.display_name}] Hoàn tất tác vụ đóng góp KNB.")
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Điều phối đầy đủ quy trình đóng góp KNB: pre, open, run, close và post."""
    if not pre_knb(steps, log):
        return steps

    log(f"[{account.display_name}] Bắt đầu quy trình đóng góp KNB.")

    try:
        if not open_knb(worker, account, device, log, screenshot=screenshot):
            log(f"[{account.display_name}] Không mở được giao diện đóng góp KNB; giữ nguyên step.")
            return steps

        skipped_templates = set()
        if not run_knb(worker, account, device, log, skipped_templates):
            return steps

        if not close_knb(worker, account, device, log, skipped_templates):
            log(f"[{account.display_name}] Chưa xác nhận được màn hình Quân đoàn; giữ nguyên step.")
            return steps

        return post_knb(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình đóng góp KNB phát sinh lỗi: {exc}")
        return steps
