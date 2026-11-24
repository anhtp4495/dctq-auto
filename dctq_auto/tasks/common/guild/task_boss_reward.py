"""Điều phối tác vụ nhận thưởng Boss trong màn hình Quân đoàn."""

import time
from enum import Enum

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_NHAN_THUONG_BOSS,
    _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_BOSS_CHUA_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_LOI_VAO_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_CHUAN_BI_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_BOSS,
    _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.battle.battle_utils import click_match, swipe, tap
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.guild.polling.boss_reward_poller import BossRewardPoller


_POLLER = BossRewardPoller()


_MAX_OPEN_TRIES = 6
_MAX_OPEN_REWARD_TRIES = 6


class _OpenRewardResult(Enum):
    OPENED = "opened"
    ALREADY_CLAIMED = "already_claimed"
    FAILED = "failed"


def pre_run_boss_reward(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ nhận thưởng Boss hay không."""
    if _STEP_QUAN_DOAN_NHAN_THUONG_BOSS not in steps:
        log("Nhận thưởng Boss: không có step trong danh sách; bỏ qua.")
        return False

    log("Nhận thưởng Boss: tìm thấy step; bắt đầu thực hiện.")
    return True


def _find_template(screen_bgr, templates, template_names, account, log):
    """Lấy observation đã phân loại từ poller chuyên biệt của tác vụ."""
    observation = _POLLER.poll(
        screen_bgr, templates, template_names, account, log
    )
    return observation["template_name"], observation["match"]

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
        _TEMPLATE_QUAN_DOAN_BOSS_LOI_VAO_NHAN_THUONG,
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

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_LOI_VAO_NHAN_THUONG:
            log(
                f"[{account.display_name}] Đã xác nhận mở "
                "[Chiến trận Quân đoàn]."
            )
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN:
            try:
                x, y = click_match(device, match)
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không click được lối vào Boss: {exc}"
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
                start = positions.get("quan_doan", "item_2")
                end = positions.get("quan_doan", "item_1")
                swipe(
                    device, start, end, account=account, log=log, duration_ms=500
                )
                start_x, start_y = start
                end_x, end_y = end
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
        time.sleep(1.8)

    log(
        f"[{account.display_name}] Mở [Chiến trận Quân đoàn] thất bại "
        f"sau {_MAX_OPEN_TRIES} lần kiểm tra."
    )
    return False


def open_reward(worker, account, device, log, screenshot=None) -> _OpenRewardResult:
    """Mở màn hình nhận thưởng hoặc xác định phần thưởng đã được nhận."""
    template_names = (
        _TEMPLATE_QUAN_DOAN_BOSS_CHUAN_BI_NHAN_THUONG,
        _TEMPLATE_QUAN_DOAN_BOSS_CHUA_NHAN_THUONG,
        _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH,
    )
    templates = get_templates(template_names)

    handled_open_reward = False
    for attempt in range(1, _MAX_OPEN_REWARD_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi mở màn hình nhận thưởng Boss.")
            return _OpenRewardResult.FAILED

        if attempt == 1 and screenshot is not None:
            try:
                screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
            except Exception as exc:
                log(f"[{account.display_name}] Không xử lý được screenshot nhận thưởng Boss: {exc}")
                return _OpenRewardResult.FAILED
        else:
            screen_bgr = _capture_screen(
                device, account, log, "khi mở màn hình nhận thưởng Boss"
            )
            if screen_bgr is None:
                return _OpenRewardResult.FAILED

        template_name, match = _find_template(
            screen_bgr, templates, template_names, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_CHUAN_BI_NHAN_THUONG:
            log(f"[{account.display_name}] Đã mở màn hình [Nhận thưởng Boss].")
            return _OpenRewardResult.OPENED

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH:
            log(
                f"[{account.display_name}] Boss Quân đoàn không còn lối nhận thưởng; "
                "xác định phần thưởng đã được nhận."
            )
            return _OpenRewardResult.ALREADY_CLAIMED

        if handled_open_reward == False and template_name == _TEMPLATE_QUAN_DOAN_BOSS_CHUA_NHAN_THUONG:
            x = round((match.left + match.right) / 2)
            y = round((match.top + match.bottom) / 2)
            try:
                tap(device, (x, y), account=account, log=log)
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không click được lối vào nhận thưởng "
                    f"tại ({x}, {y}): {exc}"
                )
                return _OpenRewardResult.FAILED

            log(
                f"[{account.display_name}] Đã click lối vào [Nhận thưởng] "
                f"tại ({x}, {y}); chờ màn hình nhận thưởng."
            )
            time.sleep(0.8)
            handled_open_reward = True
            continue

        time.sleep(1.8)

        log(
            f"[{account.display_name}] Chưa nhận diện được trạng thái Boss "
            f"(lần {attempt}/{_MAX_OPEN_REWARD_TRIES})."
        )
        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không mở được màn hình [Nhận thưởng Boss] "
        f"sau {_MAX_OPEN_REWARD_TRIES} lần kiểm tra."
    )
    return _OpenRewardResult.FAILED


def run_boss_reward(worker, account, device, log) -> bool:
    """Nhận toàn bộ thưởng Boss cho đến khi hai lần vuốt liên tiếp không còn thưởng."""
    claim_template_names = (_TEMPLATE_QUAN_DOAN_BOSS_NHAN_THUONG,)
    exit_template_names = (_TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_NHAN_THUONG,)
    templates = get_templates(claim_template_names + exit_template_names)
    positions = ButtonPositions()
    empty_swipes = 0

    log(f"[{account.display_name}] Bắt đầu nhận thưởng Boss.")

    while empty_swipes < 1:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng trong khi nhận thưởng Boss.")
            return False

        screen_bgr = _capture_screen(
            device, account, log, "khi nhận thưởng Boss"
        )
        if screen_bgr is None:
            return False

        template_name, match = _find_template(
            screen_bgr, templates, claim_template_names, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_NHAN_THUONG:
            try:
                x, y = click_match(device, match)
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không click được nút [Nhận thưởng] "
                    f"tại ({(match.left + match.right) // 2}, "
                    f"{(match.top + match.bottom) // 2}): {exc}"
                )
                return False

            log(
                f"[{account.display_name}] Đã click [Nhận thưởng] tại "
                f"({x}, {y}); chờ 0.8 giây rồi chụp và tìm lại."
            )
            time.sleep(0.8)
            continue

        # Chỉ vuốt khi ảnh hiện tại không còn nút nhận thưởng.
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng trước khi vuốt danh sách thưởng Boss.")
            return False

        try:
            start = positions.get("quan_doan", "boss_item_2")
            end = positions.get("quan_doan", "boss_item_1")
            swipe(device, start, end, account=account, log=log, duration_ms=500)
            start_x, start_y = start
            end_x, end_y = end
        except Exception as exc:
            log(
                f"[{account.display_name}] Không vuốt được danh sách thưởng Boss "
                f"từ boss_item_2 sang boss_item_1: {exc}"
            )
            return False

        empty_swipes += 1
        log(
            f"[{account.display_name}] Không còn nút [Nhận thưởng]; đã vuốt "
            f"danh sách từ boss_item_2 ({start_x}, {start_y}) lên "
            f"boss_item_1 ({end_x}, {end_y}) "
            f"(lần {empty_swipes}/2); chờ rồi kiểm tra lại."
        )
        time.sleep(0.8)

        # Chụp và tìm lại sau mỗi lần vuốt. Nếu có thưởng, quay lại vòng
        # click; bộ đếm chỉ tính các lần vuốt liên tiếp không có thưởng.
        screen_bgr = _capture_screen(
            device, account, log, "sau khi vuốt danh sách thưởng Boss"
        )
        if screen_bgr is None:
            return False

        template_name, _ = _find_template(
            screen_bgr, templates, claim_template_names, account, log
        )
        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_NHAN_THUONG:
            empty_swipes = 0

    # Hai lần vuốt liên tiếp đều không còn nút nhận thưởng.
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng trước khi đóng màn hình nhận thưởng.")
        return False

    screen_bgr = _capture_screen(
        device, account, log, "trước khi đóng màn hình nhận thưởng"
    )
    if screen_bgr is None:
        return False

    template_name, match = _find_template(
        screen_bgr, templates, exit_template_names, account, log
    )
    if template_name != _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_NHAN_THUONG:
        log(
            f"[{account.display_name}] Đã vuốt 2 lần liên tiếp không thấy nút "
            "[Nhận thưởng] nhưng không tìm thấy nút thoát màn hình nhận thưởng."
        )
        return False

    try:
        x, y = click_match(device, match)
    except Exception as exc:
        log(
            f"[{account.display_name}] Không click được nút thoát màn hình "
            f"nhận thưởng: {exc}"
        )
        return False

    log(
        f"[{account.display_name}] Đã nhận hết thưởng Boss và click nút "
        f"thoát màn hình nhận thưởng tại ({x}, {y})."
    )
    return True

def close_boss_reward(worker, account, device, log) -> bool:
    """Đóng giao diện Boss và xác nhận đã trở về màn hình Quân đoàn."""
    template_names = (
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
        _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_BOSS,
    )
    templates = get_templates(template_names)

    for attempt in range(1, 4):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đóng giao diện Boss.")
            return False

        screen_bgr = _capture_screen(
            device, account, log, "khi đóng giao diện Boss"
        )
        if screen_bgr is None:
            return False

        template_name, match = _find_template(
            screen_bgr, templates, template_names, account, log
        )

        if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
            log(
                f"[{account.display_name}] Đã thoát [Chiến trận Quân đoàn], "
                "trở về màn hình [Quân đoàn]."
            )
            return True

        if template_name == _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_BOSS:
            try:
                x, y = click_match(device, match)
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không click được nút thoát Boss: {exc}"
                )
                return False

            log(
                f"[{account.display_name}] Click nút thoát [Chiến trận Quân đoàn] "
                f"tại ({x}, {y}) — lần {attempt}/3."
            )
            time.sleep(0.8)
            continue

        log(
            f"[{account.display_name}] Không nhận diện được màn hình Boss "
            f"hoặc màn hình Quân đoàn khi đóng (lần {attempt}/3)."
        )
        time.sleep(0.8)

    log(
        f"[{account.display_name}] Đóng [Chiến trận Quân đoàn] thất bại "
        "sau 3 lần kiểm tra."
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

        reward_result = open_reward(worker, account, device, log)
        if reward_result == _OpenRewardResult.ALREADY_CLAIMED:
            close_boss_reward(worker, account, device, log)
            return post_run_boss_reward(steps, account, log)
        if reward_result != _OpenRewardResult.OPENED:
            return steps

        if not run_boss_reward(worker, account, device, log):
            return steps

        if not close_boss_reward(worker, account, device, log):
            return steps

        return post_run_boss_reward(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình nhận thưởng Boss phát sinh lỗi: {exc}")
        return steps
