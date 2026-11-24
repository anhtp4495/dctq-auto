from dctq_auto.config.constants import _STEP_QUAN_DOAN_CAU_VAN
"""Poller Cầu vận: nhận diện lối vào, lượt cầu và các trạng thái kết thúc."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
)
from .base_poller import BaseGuildPoller


class BlessingPoller(BaseGuildPoller):
    step_id = _STEP_QUAN_DOAN_CAU_VAN
    task_module = "task_blessing"

    category_key = "cau_van"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_CAU_VAN: "entry",
        _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN: "can_bless",
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1: "no_turns_1",
        _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2: "no_turns_2",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CAU_VAN: "blessing_screen",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
        _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH: "not_checked_in",
        _TEMPLATE_QUAN_DOAN_DA_BAO_DANH: "checked_in",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "entry", "can_bless", "blessing_screen"
        }
        observation["completed"] = observation["state"] in {
            "no_turns_1", "no_turns_2", "guild_main"
        }
        return observation
