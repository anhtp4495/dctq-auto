"""Poller Túi phúc: phân biệt trạng thái nhận, chi tiết và màn hình nhận."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_TUI_PHUC_CHI_TIET,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from .base_poller import BaseGuildPoller


class LuckyBagPoller(BaseGuildPoller):
    category_key = "tui_phuc"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC: "already_received",
        _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC: "not_received",
        _TEMPLATE_QUAN_DOAN_TUI_PHUC_CHI_TIET: "detail",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_NHAN_TUI_PHUC: "receive_screen",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "not_received", "detail", "receive_screen"
        }
        observation["completed"] = observation["state"] in {"already_received", "guild_main"}
        return observation
