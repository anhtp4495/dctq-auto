"""Điều phối các tác vụ thuộc màn hình [Giao Tranh]."""

from dctq_auto.config.constants import _STEP_QUAN_SU_GIAO_TRANH


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Tạm thời bỏ qua Giao Tranh bằng cách loại step khỏi danh sách."""
    if _STEP_QUAN_SU_GIAO_TRANH in steps:
        steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
        log(f"[{account.username}] Giao Tranh: tạm thời bỏ qua.")
    return steps
