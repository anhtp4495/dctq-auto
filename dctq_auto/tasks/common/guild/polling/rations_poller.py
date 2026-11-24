"""Poller nhận diện trạng thái của quy trình đóng góp Lương thảo."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_XAC_NHAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)

from .base_poller import BaseGuildPoller


# KNB được ưu tiên trước Dùng nhanh để không thao tác tiếp khi đã hiện thông báo KNB.
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_XAC_NHAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
)
_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)


class RationsPoller(BaseGuildPoller):
    """Chỉ nhận diện và trả observation; không thực hiện thao tác thiết bị."""

    step_id = _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO
    category_key = "dong_gop_luong_thao"

    state_by_template = {
        _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO: "not_donated",
        _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO: "donated",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO: "donation_screen",
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB: "buy_rations",
        _TEMPLATE_QUAN_DOAN_DUNG_NHANH: "stop_quickly",
        _TEMPLATE_QUAN_DOAN_XAC_NHAN_DUNG_NHANH: "confirm_stop_quickly",
        _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO: "close_donation_screen",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        """Nhận diện một trạng thái Lương thảo và trả về observation."""
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "not_donated",
            "donation_screen",
            "buy_rations",
            "stop_quickly",
            "confirm_stop_quickly",
            "close_donation_screen",
            "guild_main",
        }
        observation["completed"] = observation["state"] == "guild_main"
        return observation
