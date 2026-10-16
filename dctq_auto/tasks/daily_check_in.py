"""Điểm danh hằng ngày.

Dùng cho hành động Điểm danh trong tab nhiệm vụ hằng ngày.
"""
from .base import TaskSpec

SPEC = TaskSpec(
    key="diem_danh",
    label="Điểm danh",
    description="Thực hiện điểm danh hằng ngày trong game.",
    category="daily",
)
