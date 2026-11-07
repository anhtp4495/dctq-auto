"""Điều phối tác vụ đóng góp Lương thảo trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 10
_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
)
_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
)


def pre_donate_rations(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ đóng góp Lương thảo hay không."""
    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO not in steps:
        log("Đóng góp Lương thảo: không có step trong danh sách; bỏ qua.")
        return False

    log("Đóng góp Lương thảo: tìm thấy step; bắt đầu thực hiện.")
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


def _tap_match_center(device, matched, account, log, label: str) -> bool:
    """Click trung điểm template; không tiếp tục nếu thao tác ADB lỗi."""
    x = (matched.left + matched.right) // 2
    y = (matched.top + matched.bottom) // 2
    try:
        device.shell(f"input tap {x} {y}")
    except Exception as exc:
        log(f"[{account.display_name}] Không click được {label} tại ({x}, {y}): {exc}")
        return False

    log(f"[{account.display_name}] Click trung điểm {label} tại ({x}, {y}).")
    return True


def _tap_button(device, account, log, button_name: str, label: str) -> bool:
    """Click vị trí cấu hình của một nút trong màn hình Lương thảo."""
    x, y = ButtonPositions().get("quan_doan.luong_thao", button_name)
    try:
        device.shell(f"input tap {x} {y}")
    except Exception as exc:
        log(f"[{account.display_name}] Không click được {label} tại ({x}, {y}): {exc}")
        return False

    log(f"[{account.display_name}] {label} tại ({x}, {y}).")
    return True


def open_donate_rations(worker, account, device, log, screenshot=None) -> bool:
    """Điều hướng tới giao diện đóng góp và xác nhận đã nhận diện được trạng thái."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình đóng góp Lương thảo.")
    templates = get_templates(_OPEN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi mở màn hình đóng góp Lương thảo.")
            return False

        if current_try == 1 and screenshot is not None:
            try:
                screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
            except Exception as exc:
                log(f"[{account.display_name}] Không xử lý được screenshot khi mở đóng góp: {exc}")
                return False
        else:
            screen_bgr = _capture_screen(device, account, log, "khi mở đóng góp Lương thảo")
            if screen_bgr is None:
                return False

        template_name, matched = _find_template(
            screen_bgr, templates, _OPEN_TEMPLATES, account, log
        )

        if template_name is None:
            log(
                f"[{account.display_name}] Chưa nhận diện được giao diện đóng góp "
                f"(lần {current_try}/{_MAX_TRIES})."
            )
        elif template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            if not _tap_match_center(device, matched, account, log, "giao diện chính Quân đoàn"):
                return False
        elif template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO:
            if not _tap_button(device, account, log, "dong_gop", "Mở phần đóng góp Lương thảo"):
                return False
        else:
            log(f"[{account.display_name}] Đã nhận diện được giao diện đóng góp Lương thảo.")
            return True

        time.sleep(0.8)

    log(f"[{account.display_name}] Không mở được giao diện đóng góp sau {_MAX_TRIES} lần thử.")
    return False


def run_donate_rations(worker, account, device, log) -> bool:
    """Thực hiện đóng góp; chỉ thành công khi xác nhận đã đóng góp hoặc không đủ tài nguyên."""
    templates = get_templates(_RUN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đóng góp Lương thảo đã dừng theo yêu cầu.")
            return False

        screen_bgr = _capture_screen(device, account, log, "đóng góp Lương thảo")
        if screen_bgr is None:
            return False

        template_name, matched = _find_template(
            screen_bgr, templates, _RUN_TEMPLATES, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO:
            log(f"[{account.display_name}] Đã xác nhận đóng góp Lương thảo.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO:
            if not _tap_match_center(device, matched, account, log, "nút đóng góp Lương thảo"):
                return False
        elif template_name == _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB:
            if not _tap_button(device, account, log, "dong_man_hinh", "Hủy thông báo không đủ Lương thảo"):
                return False
            time.sleep(1.5)
            if not _tap_button(device, account, log, "dong_man_hinh", "Đóng thông báo không đủ Lương thảo"):
                return False
            log(f"[{account.display_name}] Không đủ tài nguyên; kết thúc thao tác đóng góp.")
            return True
        elif template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO:
            if not _tap_button(device, account, log, "dong_gop", "Thực hiện đóng góp Lương thảo"):
                return False
        elif template_name == _TEMPLATE_QUAN_DOAN_DUNG_NHANH:
            if not _tap_button(device, account, log, "xac_nhan", "Xác nhận dùng nhanh túi lúa"):
                return False
        else:
            log(
                f"[{account.display_name}] Không nhận diện được trạng thái đóng góp "
                f"(lần {current_try}/{_MAX_TRIES}); thử lại."
            )

        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không xác nhận được hoàn tất đóng góp Lương thảo "
        f"sau {_MAX_TRIES} lần thử; giữ nguyên step."
    )
    return False


def close_donate_rations(worker, account, device, log) -> bool:
    """Đóng giao diện đóng góp và xác nhận đã trở về màn hình Quân đoàn."""
    templates = get_templates(_CLOSE_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đóng giao diện đóng góp Lương thảo.")
            return False

        screen_bgr = _capture_screen(device, account, log, "khi đóng giao diện đóng góp")
        if screen_bgr is None:
            return False

        template_name, matched = _find_template(
            screen_bgr, templates, _CLOSE_TEMPLATES, account, log
        )

        if template_name in (
            _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
            _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
        ):
            log(f"[{account.display_name}] Đã xác nhận đóng giao diện đóng góp Lương thảo.")
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO:
            if not _tap_match_center(
                device, matched, account, log, "nút đóng màn hình đóng góp Lương thảo"
            ):
                return False
        elif template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO:
            if not _tap_button(
                device, account, log, "dong_man_hinh", "Đóng màn hình đóng góp Lương thảo"
            ):
                return False
        else:
            log(
                f"[{account.display_name}] Chưa xác nhận được trạng thái đóng giao diện "
                f"(lần {current_try}/{_MAX_TRIES})."
            )

        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không xác nhận được đã đóng giao diện đóng góp "
        f"sau {_MAX_TRIES} lần thử."
    )
    return False


def post_donate_rations(steps, account, log) -> list[str]:
    """Loại step sau khi đã hoàn tất đóng góp và đóng giao diện thành công."""
    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in steps:
        steps.remove(_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO)
    log(f"[{account.display_name}] Hoàn tất tác vụ đóng góp Lương thảo.")
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Điều phối đầy đủ quy trình đóng góp Lương thảo: pre, open, run, close và post."""
    if not pre_donate_rations(steps, log):
        return steps

    log(f"[{account.display_name}] Bắt đầu quy trình đóng góp Lương thảo.")

    try:
        if not open_donate_rations(
            worker, account, device, log, screenshot=screenshot
        ):
            log(f"[{account.display_name}] Không mở được giao diện đóng góp; giữ nguyên step.")
            return steps

        if not run_donate_rations(worker, account, device, log):
            return steps

        if not close_donate_rations(worker, account, device, log):
            log(f"[{account.display_name}] Chưa đóng được giao diện đóng góp; giữ nguyên step.")
            return steps

        return post_donate_rations(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình đóng góp Lương thảo phát sinh lỗi: {exc}")
        return steps
