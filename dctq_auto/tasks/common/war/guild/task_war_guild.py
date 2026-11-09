"""Điều phối mở, nhận thưởng và đóng giao diện Đoàn Chiến."""

from datetime import datetime

from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG
from dctq_auto.tasks.common.war.guild import (
    task_close_war_guild,
    task_open_war_guild,
    task_run_war_guild,
)
from dctq_auto.tasks.common.war.three_kingdom import task_run_three_kingdom


def pre_war_guild(steps, log) -> bool:
    """Chỉ nhận thưởng Đoàn Chiến vào thứ Hai hoặc thứ Ba khi step được chọn."""
    if _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG not in steps:
        log("Đoàn Chiến: không có step nhận thưởng trong danh sách; bỏ qua.")
        return False

    weekday = datetime.now().weekday()
    if weekday not in (0, 1):
        day_name = ("thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ Nhật")[weekday]
        log(f"Đoàn Chiến: chỉ chạy vào thứ Hai hoặc thứ Ba (hôm nay là {day_name}); bỏ qua.")
        return False

    log("Đoàn Chiến: tìm thấy step nhận thưởng và hôm nay là thứ Hai/thứ Ba; sẵn sàng.")
    return True


def post_war_guild(steps, log) -> list[str]:
    """Gỡ step nhận thưởng Đoàn Chiến khỏi danh sách sau khi xử lý."""
    if _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG in steps:
        steps.remove(_STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG)
        log("Đoàn Chiến: đã gỡ step nhận thưởng khỏi danh sách steps.")
    return steps


def run(worker, account, steps: list[str], device, log) -> list[str]:
    """Điều phối nhận thưởng Đoàn Chiến, Tam Quan và cập nhật danh sách steps."""
    if not pre_war_guild(steps, log):
        return post_war_guild(steps, log)

    log(f"[{account.display_name}] Bắt đầu quy trình nhận thưởng Đoàn Chiến.")
    try:
        if not task_open_war_guild.run(worker, account, device, log):
            return steps

        try:
            received_guild = task_run_war_guild.run(worker, account, device, log)
            received_three_kingdom = task_run_three_kingdom.run(
                worker, account, device, log
            )
        finally:
            closed = task_close_war_guild.run(worker, account, device, log)

        if not closed:
            log(f"[{account.display_name}] Chưa xác nhận đóng được màn hình Đoàn Chiến.")
        else:
            if received_guild:
                log(f"[{account.display_name}] Đã hoàn tất nhận thưởng Đoàn Chiến.")
            if received_three_kingdom:
                log(f"[{account.display_name}] Đã hoàn tất nhận thưởng Tam Quan.")
        return steps
    finally:
        post_war_guild(steps, log)
