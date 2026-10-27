"""Các hàm báo cáo kết quả template matching dùng chung."""

from __future__ import annotations

from typing import Callable

from dctq_auto.vision.template_matching import TemplateMatch


def report_template_match(
    emit_log: Callable[[str], object],
    *,
    context: str,
    template_name: str,
    display_name: str,
    match: TemplateMatch,
    threshold: float,
) -> None:
    """Ghi log thống nhất khi một template khớp ảnh màn hình.

    Truyền worker.log_message.emit làm emit_log để hàm không phụ thuộc GUI/worker.
    """
    emit_log(
        f"{context} Template {template_name} ({display_name}) khớp "
        f"(score={match.score:.3f}, threshold={threshold:.3f}, rect={match.rect})."
    )
