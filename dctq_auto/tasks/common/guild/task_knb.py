"""Tác vụ đóng góp KNB trong Quân đoàn."""

from dctq_auto.config.constants import _STEP_QUAN_DOAN_DONG_GOP_KNB


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Chạy tác vụ đóng góp KNB và loại step khi tác vụ hoàn tất."""
    if _STEP_QUAN_DOAN_DONG_GOP_KNB not in steps:
        return steps

    if worker._run_guild_screen_task("task_donate_knb", device, ocr_client):
        steps.remove(_STEP_QUAN_DOAN_DONG_GOP_KNB)

    return steps
