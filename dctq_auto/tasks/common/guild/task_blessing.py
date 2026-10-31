"""Tác vụ Cầu vận (blessing) trong Quân đoàn."""

from dctq_auto.config.constants import _STEP_QUAN_DOAN_CAU_VAN


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Tạm bỏ qua Cầu vận khi tác vụ chưa được triển khai."""
    if _STEP_QUAN_DOAN_CAU_VAN not in steps:
        return steps

    log(
        f"[{account.username}] Cầu vận trong Quân đoàn hiện chưa triển khai; "
        "bỏ qua step."
    )
    steps.remove(_STEP_QUAN_DOAN_CAU_VAN)
    return steps
