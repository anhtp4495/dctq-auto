"""Điều phối mở, nhận thưởng và đóng giao diện Đoàn Chiến."""

from dctq_auto.tasks.common.war.guild import (
    task_close_war_guild,
    task_open_war_guild,
    task_run_war_guild,
)


def run(worker, account, device, log) -> bool:
    """Chạy trọn quy trình nhận thưởng Đoàn Chiến bằng Template Matching."""
    log(f"[{account.display_name}] Bắt đầu quy trình nhận thưởng Đoàn Chiến.")
    if not task_open_war_guild.run(worker, account, device, log):
        return False

    received = False
    try:
        received = task_run_war_guild.run(worker, account, device, log)
        return received
    finally:
        closed = task_close_war_guild.run(worker, account, device, log)
        if not closed:
            log(f"[{account.display_name}] Cảnh báo: chưa xác nhận đóng được màn hình Đoàn Chiến.")
