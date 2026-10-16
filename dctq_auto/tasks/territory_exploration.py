"""Thăm dò lãnh địa: hành động thăm dò và tùy chọn mua lượt bằng KNB."""
from .base import TaskSpec

SPEC = TaskSpec(key="tham_do_lanh_dia", label="Thăm dò lãnh địa", description="Thăm dò lãnh địa theo số lượt; có tùy chọn mua lượt bằng KNB.", category="daily", count_key="so_lan_tham_do_lanh_dia")
