"""Poller Cầu vận: chỉ nhận diện các trạng thái của tác vụ."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
    _TEMPLATE_QUAN_DOAN_THOAT_MAN_HINH_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from .base_poller import BaseGuildPoller


class BlessingPoller(BaseGuildPoller):
    step_id = _STEP_QUAN_DOAN_CAU_VAN

    category_key = "cau_van"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_CAU_VAN: "entry",
        _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN: "can_bless",
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1: "no_turns_1",
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2: "no_turns_2",
        _TEMPLATE_QUAN_DOAN_THOAT_MAN_HINH_CAU_VAN: "exit_blessing",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "entry", "can_bless", "exit_blessing"
        }
        observation["completed"] = observation["state"] == "guild_main"
        return observation
