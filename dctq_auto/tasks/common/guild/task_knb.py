"""Tác vụ đóng góp KNB trong Quân đoàn."""

from dctq_auto.config.constants import _STEP_QUAN_DOAN_DONG_GOP_KNB


def run(
    worker, account, steps, device, ocr_client, log, screenshot=None,
) -> list[str]:
    """Tạm bỏ qua đóng góp KNB khi tác vụ chưa được triển khai."""
    if _STEP_QUAN_DOAN_DONG_GOP_KNB not in steps:
        return steps

    log(
        f"[{account.username}] Đóng góp KNB trong Quân đoàn hiện chưa triển khai; "
        "bỏ qua step."
    )
    steps.remove(_STEP_QUAN_DOAN_DONG_GOP_KNB)
    return steps
