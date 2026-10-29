"""Điều phối các bước thuộc màn hình Quân đoàn."""

from dctq_auto.tasks.common.guild import (
    task_blessing,
    task_close_guild,
    task_daily_check_in,
    task_donate_rations,
    task_knb,
    task_lucky_bag,
    task_open_guild,
)

_GUILD_STEP_IDS = {
    "quan_doan_bao_danh",
    "quan_doan_tui_phuc",
    "quan_doan_cau_van",
    "quan_doan_dong_gop_luong_thao",
    "quan_doan_dong_gop_knb",
}

_TASKS = (
    ("quan_doan_bao_danh", "Báo danh quân đoàn", task_daily_check_in.run),
    ("quan_doan_tui_phuc", "Nhận túi phúc", task_lucky_bag.run),
    ("quan_doan_cau_van", "Cầu vận quân đoàn (5 lần)", task_blessing.run),
    ("quan_doan_dong_gop_luong_thao", "Đóng góp lương thảo", task_donate_rations.run),
    ("quan_doan_dong_gop_knb", "Đóng góp KNB", task_knb.run),
)


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Quân đoàn, chạy các bước được chọn và luôn thử thoát trong finally."""
    selected_steps = _GUILD_STEP_IDS.intersection(steps)
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
