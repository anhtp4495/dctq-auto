"""Poller đóng góp KNB: nhận diện cửa vào, điều kiện và các mức đóng góp."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from .base_poller import BaseGuildPoller


class KnbPoller(BaseGuildPoller):
    category_key = "dong_gop_knb"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB: "entry",
        _TEMPLATE_QUAN_DOAN_CHUA_DU_DIEU_KIEN_DONG_GOP_KNB: "insufficient_conditions",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_KNB: "donation_screen",
        _TEMPLATE_QUAN_DOAN_DONG_GOP_10_KNB: "donate_10",
        _TEMPLATE_QUAN_DOAN_DONG_GOP_20_KNB: "donate_20",
        _TEMPLATE_QUAN_DOAN_DONG_GOP_40_KNB: "donate_40",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "entry", "donation_screen", "donate_10", "donate_20", "donate_40"
        }
        observation["completed"] = observation["state"] in {"insufficient_conditions", "guild_main"}
        return observation
