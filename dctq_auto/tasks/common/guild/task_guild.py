"""Điều phối các bước thuộc màn hình [Quân đoàn]."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
)
from dctq_auto.tasks.common.guild import task_close_guild, task_open_guild

_GUILD_STEP_IDS = {
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
}

def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Quân đoàn, chạy các bước được chọn, rồi đóng màn hình.

    Các bước thành công được loại khỏi danh sách steps tại chỗ. Bước thất bại
    và các bước chưa chạy được giữ lại để luồng Clone có thể thử lại.
    """
    guild_open_attempted = False
    try:
        selected_steps = _GUILD_STEP_IDS.intersection(steps)
        if not selected_steps:
            return steps

        guild_open_attempted = True
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình [Quân đoàn]; giữ nguyên các bước.")
            return steps

        steps_run(worker, account, steps, device, ocr_client, log)
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")

    return steps

def steps_run( worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    return worker._run_guild_screen_task("task_receive_lucky_bag", device, ocr_client)