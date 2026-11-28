"""Poller nhận diện trạng thái nhận thưởng Đoàn Chiến và Tam Quân."""

from dctq_auto.config.constants import (
    _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DONG_TONG_KET,
)
from dctq_auto.tasks.common.guild.polling.base_poller import BaseGuildPoller


class GuildWarRewardPoller(BaseGuildPoller):
    """Chỉ matching template và trả observation; không click hay điều khiển flow."""

    step_id = _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG
    category_key = "guild_war_reward"

    state_by_template = {
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG: "reward_claimed",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG: "reward_available",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG: "tap_blank_to_claim",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT: "tap_blank_to_exit",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET: "summary_screen",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET: "close_summary",
        _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DA_NHAN_THUONG: "tam_quan_reward_claimed",
        _TEMPLATE_CHIEN_TRANH_TAM_QUAN_CHUA_NHAN_THUONG: "tam_quan_reward_available",
        _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DONG_TONG_KET: "close_tam_quan_summary",
    }

    template_names = tuple(state_by_template)

    def check(self, context) -> dict:
        return self._match_first({**context, "template_names": self.template_names})
