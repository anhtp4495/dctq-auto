"""Điều phối mở, nhận thưởng và bổ sung phòng thủ Đoàn Chiến."""

import time
from datetime import datetime

from dctq_auto.config.constants import (
    _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG,
    _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_QUYEN_GOP,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, screen_bgr
from dctq_auto.tasks.common.war.guild import (
    task_close_war_guild,
    task_open_war_guild,
    task_run_war_guild,
)
from dctq_auto.tasks.common.war.guild.polling import DefenseReinforcementPoller
from dctq_auto.vision.template_store import get_templates


_POLL_INTERVAL = 0.8
_POLL_TIMEOUT_SECONDS = 180
_MAX_CONTRIBUTIONS = 30

_MAIN_SCREEN = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH
_CONTRIBUTE = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_QUYEN_GOP
_CONFIRM = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN
_RESOURCES_EXHAUSTED = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN
_EXIT = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT


def _defense_reinforcement_is_due(now: datetime) -> bool:
    """Thứ Năm từ 07:00 đến hết thứ Sáu 23:00."""
    if now.weekday() == 3:
        return now.hour >= 7
    if now.weekday() == 4:
        return (now.hour, now.minute) <= (23, 0)
    return False


def _reward_is_due(now: datetime) -> bool:
    return now.weekday() in (0, 1)


def pre_war_guild(steps, log, now=None) -> bool:
    """Kiểm tra các tác vụ Đoàn Chiến đang đến lịch chạy."""
    now = now or datetime.now()
    reward_due = (
        _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG in steps
        and _reward_is_due(now)
    )
    defense_due = (
        _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU in steps
        and _defense_reinforcement_is_due(now)
    )
    if reward_due:
        log("Đoàn Chiến: đã đến lịch nhận thưởng thứ Hai/thứ Ba.")
    if defense_due:
        log("Đoàn Chiến: đã đến lịch bổ sung phòng thủ (thứ Năm 07:00 đến thứ Sáu 23:00).")
    if not reward_due and not defense_due:
        log("Đoàn Chiến: hiện không có tác vụ nào đến lịch chạy.")
    return reward_due or defense_due


def post_war_guild(steps, log) -> list[str]:
    """Gỡ step nhận thưởng sau khi đã đến đợt xử lý."""
    if _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG in steps:
        steps.remove(_STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG)
        log("Đoàn Chiến: đã gỡ step nhận thưởng khỏi danh sách steps.")
    return steps


def _run_defense_reinforcement(worker, account, device, log) -> bool:
    """Quyên góp phòng thủ tối đa 30 lần rồi thoát màn hình."""
    poller = DefenseReinforcementPoller()
    phase = "prepare"
    contribution_count = 0
    template_names = (_MAIN_SCREEN,)
    templates = get_templates(template_names)
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    log(f"[{account.display_name}] Bắt đầu bổ sung phòng thủ Đoàn Chiến.")
    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Bổ sung phòng thủ đã dừng theo yêu cầu.")
            return False

        screen = screen_bgr(device)
        observation = poller.poll(screen, templates, template_names, account, log)
        state = observation["state"]

        if phase == "prepare":
            if state == "main_screen":
                phase = "contribute"
                template_names = (_RESOURCES_EXHAUSTED, _CONFIRM, _CONTRIBUTE)
                templates = get_templates(template_names)
                log(f"[{account.display_name}] Đã xác nhận màn hình Chuẩn bị - Bổ sung phòng thủ.")
        elif phase == "contribute":
            if state == "resources_exhausted":
                phase = "close"
                template_names = (_EXIT, _MAIN_SCREEN)
                templates = get_templates(template_names)
                log(f"[{account.display_name}] Đã hết tài nguyên; dừng quyên góp và chuyển sang thoát.")
            elif state == "contribute":
                x, y = click_match(device, observation["match"])
                contribution_count += 1
                log(
                    f"[{account.display_name}] Quyên góp phòng thủ "
                    f"({contribution_count}/{_MAX_CONTRIBUTIONS}) tại ({x}, {y})."
                )
                if contribution_count >= _MAX_CONTRIBUTIONS:
                    phase = "close"
                    template_names = (_EXIT, _MAIN_SCREEN)
                    templates = get_templates(template_names)
                    log(f"[{account.display_name}] Đã đủ {_MAX_CONTRIBUTIONS} lượt quyên góp; chuyển sang thoát.")
            elif state == "confirm":
                x, y = click_match(device, observation["match"])
                log(f"[{account.display_name}] Click xác nhận quyên góp tại ({x}, {y}).")
        elif phase == "close":
            if state == "exit":
                x, y = click_match(device, observation["match"])
                log(f"[{account.display_name}] Click thoát màn hình bổ sung phòng thủ tại ({x}, {y}).")
            elif state == "main_screen":
                log(
                    f"[{account.display_name}] Đã xác nhận quay lại màn hình Chuẩn bị - "
                    "Bổ sung phòng thủ; hoàn tất."
                )
                return True

        time.sleep(_POLL_INTERVAL)

    log(
        f"[{account.display_name}] Bổ sung phòng thủ quá thời gian polling "
        f"{_POLL_TIMEOUT_SECONDS} giây; giữ nguyên step."
    )
    return False


def run(worker, account, steps: list[str], device, log) -> list[str]:
    """Điều phối các tác vụ Đoàn Chiến theo lịch và cập nhật steps."""
    now = datetime.now()
    reward_selected = _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG in steps
    defense_selected = _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU in steps
    reward_due = reward_selected and _reward_is_due(now)
    defense_due = defense_selected and _defense_reinforcement_is_due(now)

    if not pre_war_guild(steps, log, now=now):
        return post_war_guild(steps, log)

    opened = False
    try:
        if not task_open_war_guild.run(worker, account, device, log):
            log(f"[{account.display_name}] Không mở được màn hình Đoàn Chiến.")
            return steps
        opened = True

        if defense_due:
            success = _run_defense_reinforcement(worker, account, device, log)
            if success and _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU in steps:
                steps.remove(_STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU)
                log(f"[{account.display_name}] Đã hoàn tất Bổ sung phòng thủ Đoàn Chiến.")

        if reward_due:
            received = task_run_war_guild.run(worker, account, device, log)
            if received:
                log(f"[{account.display_name}] Đã hoàn tất nhận thưởng Đoàn Chiến.")
    finally:
        if opened:
            closed = task_close_war_guild.run(worker, account, device, log)
            if not closed:
                log(f"[{account.display_name}] Chưa xác nhận đóng được màn hình Đoàn Chiến.")
        post_war_guild(steps, log)

    return steps
