"""Poller nhận diện trạng thái quyên góp phòng thủ Đoàn Chiến."""

from dctq_auto.config.constants import (
    _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_QUYEN_GOP,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT,
)
from dctq_auto.tasks.common.guild.polling.base_poller import BaseGuildPoller


class DefenseReinforcementPoller(BaseGuildPoller):
    """Chỉ nhận diện trạng thái và trả observation; task điều phối click."""

    step_id = _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU
    category_key = "guild_war_defense_reinforcement"

    state_by_template = {
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH: "main_screen",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_QUYEN_GOP: "contribute",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN: "confirm",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN: "resources_exhausted",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT: "exit",
    }

    template_names = tuple(state_by_template)

    def check(self, context) -> dict:
        return self._match_first({**context, "template_names": self.template_names})
