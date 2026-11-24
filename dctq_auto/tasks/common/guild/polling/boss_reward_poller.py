"""Poller Boss: phân loại điều hướng, trạng thái nhận thưởng và thoát màn hình."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_BOSS_CHUA_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_LOI_VAO_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_CHUAN_BI_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_NHAN_THUONG,
    _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_BOSS,
    _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from .base_poller import BaseGuildPoller


class BossRewardPoller(BaseGuildPoller):
    category_key = "boss_reward"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_CHINH: "boss_main",
        _TEMPLATE_QUAN_DOAN_BOSS_CHUA_NHAN_THUONG: "reward_available_entry",
        _TEMPLATE_QUAN_DOAN_BOSS_MAN_HINH_NHAN_THUONG: "reward_screen",
        _TEMPLATE_QUAN_DOAN_BOSS_LOI_VAO_NHAN_THUONG: "reward_entrance",
        _TEMPLATE_QUAN_DOAN_BOSS_CHUAN_BI_NHAN_THUONG: "ready_to_claim",
        _TEMPLATE_QUAN_DOAN_BOSS_NHAN_THUONG: "claim_button",
        _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_NHAN_THUONG: "exit_reward_screen",
        _TEMPLATE_QUAN_DOAN_BOSS_THOAT_MAN_HINH_BOSS: "exit_boss_screen",
        _TEMPLATE_QUAN_DOAN_BOSS_QUAN_DOAN: "guild_boss_entry",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "reward_available_entry", "reward_entrance", "claim_button",
            "exit_reward_screen", "exit_boss_screen", "guild_boss_entry",
        }
        observation["completed"] = observation["state"] == "boss_main"
        return observation
