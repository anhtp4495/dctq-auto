from dctq_auto.config.constants import _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO
"""Poller đóng góp Lương thảo: phân loại các trạng thái đóng góp và điều hướng."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
)
from .base_poller import BaseGuildPoller


class RationsPoller(BaseGuildPoller):
    step_id = _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO
    task_module = "task_donate_rations"

    category_key = "dong_gop_luong_thao"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO: "not_donated",
        _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO: "donated",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO: "donation_screen",
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB: "buy_rations",
        _TEMPLATE_QUAN_DOAN_DUNG_NHANH: "stop_quickly",
        _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO: "close_donation_screen",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
        _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH: "not_checked_in",
        _TEMPLATE_QUAN_DOAN_DA_BAO_DANH: "checked_in",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "not_donated", "donation_screen", "buy_rations", "stop_quickly",
            "close_donation_screen",
        }
        observation["completed"] = observation["state"] in {"donated", "guild_main"}
        return observation
