"""Tác vụ Cầu vận (blessing) trong Quân đoàn."""

from dctq_auto.config.constants import _STEP_QUAN_DOAN_CAU_VAN


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Chạy tác vụ Cầu vận và loại step khi tác vụ hoàn tất."""
    if _STEP_QUAN_DOAN_CAU_VAN not in steps:
        return steps

    if worker._run_guild_screen_task("task_guild_fortune", device, ocr_client):
        steps.remove(_STEP_QUAN_DOAN_CAU_VAN)

    return steps
