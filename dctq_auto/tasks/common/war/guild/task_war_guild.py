"""Điều phối vòng đời tác vụ Đoàn Chiến: pre, open, run, close, post."""

from datetime import datetime

from dctq_auto.config.constants import (
    _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG,
    _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU,
)
from dctq_auto.tasks.common.war.guild import (
    task_close_war_guild,
    task_open_war_guild,
    task_run_war_guild,
)


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


def post_war_guild(steps, log, now=None) -> list[str]:
    """Hook sau khi xử lý Đoàn Chiến; step được task nghiệp vụ tự cập nhật."""
    return steps


def run(worker, account, steps: list[str], device, log) -> list[str]:
    """Chỉ điều phối vòng đời Đoàn Chiến; nghiệp vụ nằm trong task_run_war_guild."""
    now = datetime.now()
    if not pre_war_guild(steps, log, now=now):
        return post_war_guild(steps, log, now=now)

    opened = False
    try:
        opened = task_open_war_guild.run(worker, account, device, log)
        if not opened:
            log(f"[{account.display_name}] Không mở được màn hình Đoàn Chiến.")
        else:
            task_run_war_guild.run(worker, account, steps, device, log)
    finally:
        if opened:
            closed = task_close_war_guild.run(worker, account, device, log)
            if not closed:
                log(f"[{account.display_name}] Chưa xác nhận đóng được màn hình Đoàn Chiến.")
        post_war_guild(steps, log, now=now)

    return steps
