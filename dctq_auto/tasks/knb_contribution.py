"""Đóng góp KNB: thực hiện hành động đóng góp KNB theo số lượt cấu hình."""
from .base import TaskSpec

SPEC = TaskSpec(key="dong_gop_knb", label="Đóng góp KNB", description="Đóng góp KNB theo số lượt cấu hình.", category="daily", count_key="so_lan_dong_gop_knb")
