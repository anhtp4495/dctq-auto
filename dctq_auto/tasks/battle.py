"""Giao tranh: bật bằng thuc_hien_giao_tranh và dùng số lượt giao_tranh."""
from .base import TaskSpec

SPEC = TaskSpec(key="giao_tranh", label="Giao tranh", description="Thực hiện các trận Giao tranh theo số lượt cấu hình.", category="battle", enabled_key="thuc_hien_giao_tranh", count_key="giao_tranh")
