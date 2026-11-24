"""Poller báo danh: phân biệt đã báo danh, chưa báo danh và màn hình Quân đoàn."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from .base_poller import BaseGuildPoller


class DailyCheckInPoller(BaseGuildPoller):
    category_key = "bao_danh"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH: "not_checked_in",
        _TEMPLATE_QUAN_DOAN_DA_BAO_DANH: "checked_in",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }
