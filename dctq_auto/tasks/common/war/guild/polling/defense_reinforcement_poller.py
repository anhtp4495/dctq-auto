"""Poller nhận diện trạng thái quyên góp phòng thủ Đoàn Chiến."""

from dctq_auto.config.constants import (
    _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_LOI_VAO,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_CONG_HIEN_BAO_CHAU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN1,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN2,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT,
    _TEMPLATE_MAIN_QUAN_SU,
)
from dctq_auto.tasks.common.guild.polling.base_poller import BaseGuildPoller


class DefenseReinforcementPoller(BaseGuildPoller):
    """Chỉ nhận diện trạng thái và trả observation; task điều phối click."""

    step_id = _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU
    category_key = "guild_war_defense_reinforcement"

    state_by_template = {
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH: "main_screen",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_LOI_VAO: "entry",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN1: "resources_exhausted",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN2: "resources_exhausted",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN: "confirm",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_CONG_HIEN_BAO_CHAU: "contribute",
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT: "exit",
        _TEMPLATE_MAIN_QUAN_SU: "completed",
    }

    template_names = tuple(state_by_template)

    def check(self, context) -> dict:
        # Task truyền danh sách template theo từng phase; không tự mở rộng danh sách.
        return self._match_first(context)
