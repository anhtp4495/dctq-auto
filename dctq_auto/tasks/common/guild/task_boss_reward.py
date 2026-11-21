"""Điều phối tác vụ nhận thưởng Boss trong màn hình Quân đoàn."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_NHAN_THUONG_BOSS,
    _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_OPEN_TRIES = 6


def pre_run_boss_reward(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ nhận thưởng Boss hay không."""
    if _STEP_QUAN_DOAN_NHAN_THUONG_BOSS not in steps:
        log("Nhận thưởng Boss: không có step trong danh sách; bỏ qua.")
        return False

    log("Nhận thưởng Boss: tìm thấy step; bắt đầu thực hiện.")
    return True


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template đầu tiên khớp theo thứ tự ưu tiên."""
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
            log(
                f"[{account.display_name}] Lỗi template matching "
                f"{template_name}: {exc}"
            )
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


def _capture_screen(device, account, log, action):
    """Chụp màn hình và chuyển sang BGR."""
    try:
        screenshot = device.screenshot()
        return cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình {action}: {exc}")
        return None


def open_boss_reward(worker, account, device, log, screenshot=None) -> bool:
    """Mở Chiến trận Quân đoàn; xác nhận màn hình đích trong tối đa 6 lần."""
    log(f"[{account.display_name}] Bắt đầu mở [Chiến trận Quân đoàn].")
    template_names = (
        _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH,
        _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN,
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    )
    templates = get_templates(template_names)
    positions = ButtonPositions()

    for current_try in range(1, _MAX_OPEN_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi mở [Chiến trận Quân đoàn].")
            return False

        if current_try == 1 and screenshot is not None:
            try:
                screen_bgr = cv2.cvtColor(
                    np.asarray(screenshot), cv2.COLOR_RGB2BGR
                )
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không xử lý được screenshot "
                    f"khi mở Boss: {exc}"
                )
                return False
        else:
            screen_bgr = _capture_screen(
                device, account, log, "khi mở [Chiến trận Quân đoàn]"
            )
            if screen_bgr is None:
                return False

        template_name, match = _find_template(
            screen_bgr, templates, template_names, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH:
            log(
                f"[{account.display_name}] Đã xác nhận mở "
                "[Chiến trận Quân đoàn]."
            )
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN:
            x = (match.left + match.right) // 2
            y = (match.top + match.bottom) // 2
            try:
                device.shell(f"input tap {x} {y}")
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không click được lối vào Boss "
                    f"tại ({x}, {y}): {exc}"
                )
                return False

            log(
                f"[{account.display_name}] Đã click trung điểm lối vào "
                f"[Boss Quân đoàn] tại ({x}, {y}); chờ màn hình đích."
            )
            time.sleep(0.8)
            continue

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            try:
                start_x, start_y = positions.get("quan_doan", "item_2")
                end_x, end_y = positions.get("quan_doan", "item_1")
                device.shell(
                    f"input swipe {start_x} {start_y} {end_x} {end_y} 500"
                )
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không vuốt được danh sách "
                    f"Quân đoàn từ item_2 sang item_1: {exc}"
                )
                return False

            log(
                f"[{account.display_name}] Chưa thấy lối vào Boss; "
                f"vuốt từ item_2 ({start_x}, {start_y}) sang "
                f"item_1 ({end_x}, {end_y}) "
                f"(lần {current_try}/{_MAX_OPEN_TRIES})."
            )
            time.sleep(0.8)
            continue

        log(
            f"[{account.display_name}] Chưa nhận diện được màn hình Quân đoàn "
            f"hoặc màn hình Boss (lần {current_try}/{_MAX_OPEN_TRIES})."
        )
        time.sleep(0.8)

    log(
        f"[{account.display_name}] Mở [Chiến trận Quân đoàn] thất bại "
        f"sau {_MAX_OPEN_TRIES} lần kiểm tra."
    )
    return False


def run_boss_reward(worker, account, device, log) -> bool:
    """Thực hiện nhận thưởng Boss; chờ triển khai template trạng thái thưởng."""
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Nhận thưởng Boss đã dừng theo yêu cầu.")
        return False

    log(
        f"[{account.display_name}] Chưa triển khai thao tác nhận thưởng Boss: "
        "cần xử lý trạng thái và nút nhận thưởng."
    )
    return False


def close_boss_reward(worker, account, device, log) -> bool:
    """Đóng giao diện Boss và xác nhận đã trở về màn hình Quân đoàn."""
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đóng giao diện Boss.")
        return False

    log(
        f"[{account.display_name}] Chưa triển khai đóng giao diện Boss: "
        "cần xử lý template thoát và xác nhận màn hình Quân đoàn."
    )
    return False


def post_run_boss_reward(steps, account, log) -> list[str]:
    """Loại step sau khi đã xác nhận nhận thưởng Boss thành công."""
    if _STEP_QUAN_DOAN_NHAN_THUONG_BOSS in steps:
        steps.remove(_STEP_QUAN_DOAN_NHAN_THUONG_BOSS)
    log(f"[{account.display_name}] Hoàn tất tác vụ nhận thưởng Boss Quân đoàn.")
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Điều phối tác vụ nhận thưởng Boss theo quy trình pre, open, run, close, post."""
    if not pre_run_boss_reward(steps, log):
        return steps

    try:
        if not open_boss_reward(worker, account, device, log, screenshot=screenshot):
            return steps

        if not run_boss_reward(worker, account, device, log):
            return steps

        if not close_boss_reward(worker, account, device, log):
            return steps

        return post_run_boss_reward(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình nhận thưởng Boss phát sinh lỗi: {exc}")
        return steps
