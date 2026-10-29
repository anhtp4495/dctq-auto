"""Điều phối các bước thuộc màn hình Quân đoàn."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
)
from dctq_auto.tasks.common.guild import (
    task_blessing,
    task_close_guild,
    task_daily_check_in,
    task_donate_rations,
    task_knb,
    task_lucky_bag,
    task_open_guild,
)

GUILD_STEP_IDS = {
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
}

_TASKS = (
    (_STEP_QUAN_DOAN_BAO_DANH, "Báo danh quân đoàn", task_daily_check_in.run),
    (_STEP_QUAN_DOAN_TUI_PHUC, "Nhận túi phúc", task_lucky_bag.run),
    (_STEP_QUAN_DOAN_CAU_VAN, "Cầu vận quân đoàn (5 lần)", task_blessing.run),
    (_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO, "Đóng góp lương thảo", task_donate_rations.run),
    (_STEP_QUAN_DOAN_DONG_GOP_KNB, "Đóng góp KNB", task_knb.run),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Quân đoàn, chạy các bước được chọn và luôn thử thoát trong finally."""
    selected_steps = GUILD_STEP_IDS.intersection(steps)
    if not selected_steps:
        return steps

    guild_open_attempted = False
    try:
        guild_open_attempted = True
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình Quân đoàn; giữ nguyên các bước.")
            return steps

        for key, label, task_runner in _TASKS:
            if key not in selected_steps:
                continue
            if not worker._wait_if_paused():
                log(f"[{account.username}] Đã dừng trước bước {label}; giữ lại các bước chưa chạy.")
                break
            try:
                if task_runner(worker, device, ocr_client):
                    steps.discard(key) if hasattr(steps, "discard") else steps.remove(key)
                    log(f"[{account.username}] Hoàn tất bước {label}.")
                else:
                    log(f"[{account.username}] Bước {label} thất bại; sẽ giữ lại để thử lại.")
            except Exception as exc:
                log(f"[{account.username}] Bước {label} phát sinh lỗi: {exc}")
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được màn hình Quân đoàn.")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi thoát màn hình Quân đoàn: {exc}")

    return steps
