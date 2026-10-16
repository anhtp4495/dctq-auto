"""Tranh bá: bật bằng thuc_hien_tranh_ba và dùng số lượt tranh_ba."""
from .base import TaskSpec

SPEC = TaskSpec(key="tranh_ba", label="Tranh bá", description="Thực hiện các trận Tranh bá theo số lượt cấu hình.", category="battle", enabled_key="thuc_hien_tranh_ba", count_key="tranh_ba")
