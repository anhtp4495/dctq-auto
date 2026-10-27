"""Các hàm báo cáo kết quả template matching dùng chung."""

from __future__ import annotations

from typing import Callable

from dctq_auto.vision.template_matching import TemplateMatch
from dctq_auto.vision.template_store import LoadedTemplate


def report_template_match(
    emit_log: Callable[[str], object],
    *,
    context: str,
    template: LoadedTemplate,
    match: TemplateMatch,
) -> None:
    """Ghi log thống nhất khi một template khớp ảnh màn hình."""
    description = f" ({template.description})" if template.description else ""
    emit_log(
        f"{context} Template {template.name}{description} khớp "
        f"(score={match.score:.3f}, threshold={template.threshold:.3f}, rect={match.rect})."
    )
