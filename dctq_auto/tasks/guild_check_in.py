"""Báo danh quân đoàn.

Dùng cho hành động Báo danh quân đoàn trong tab nhiệm vụ hằng ngày.
"""
from .base import TaskSpec

SPEC = TaskSpec(
    key="bao_danh_quan_doan",
    label="Báo danh quân đoàn",
    description="Thực hiện báo danh trong quân đoàn.",
    category="daily",
)
