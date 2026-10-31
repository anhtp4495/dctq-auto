"""Điều phối các bước thuộc màn hình [Quân đoàn]."""

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


_GUILD_STEP_IDS = {
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
}


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Quân đoàn, gọi các task con được chọn, rồi đóng màn hình."""
    selected_steps = _GUILD_STEP_IDS.intersection(steps)
    if not selected_steps:
        return steps

    guild_open_attempted = False
    try:
        guild_open_attempted = True
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình [Quân đoàn]; giữ nguyên các bước.")
            return steps

        return steps_run(
            worker, account, steps, device, ocr_client, log, screenshot=None
        )
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")


def steps_run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Lần lượt gọi các task con; mỗi task tự xử lý template và cập nhật steps."""
    task_steps = (
        (_STEP_QUAN_DOAN_BAO_DANH, task_daily_check_in, "Báo danh Quân đoàn"),
        (_STEP_QUAN_DOAN_TUI_PHUC, task_lucky_bag, "Nhận Túi phúc Quân đoàn"),
        (_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO, task_donate_rations, "Đóng góp Lương thảo"),
        (_STEP_QUAN_DOAN_DONG_GOP_KNB, task_knb, "Đóng góp KNB"),
        (_STEP_QUAN_DOAN_CAU_VAN, task_blessing, "Cầu vận Quân đoàn"),
    )

    for step, task, task_name in task_steps:
        if step not in steps:
            continue

        try:
            steps = task.run(
                worker, account, steps, device, ocr_client, log, screenshot=None
            )
        except Exception as exc:
            log(f"[{account.username}] {task_name} thất bại: {exc}")

    return steps
