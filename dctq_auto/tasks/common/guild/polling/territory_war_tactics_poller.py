"""Poller nhận diện lối vào Lãnh địa chiến trong màn hình Quân đoàn."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_LANH_DIA_CHIEN_MUU_KE,
    _TEMPLATE_QUAN_DOAN_LANH_DIA_CHIEN,
)
from .base_poller import BaseGuildPoller


class TerritoryWarTacticsPoller(BaseGuildPoller):
    """Nhận diện điểm vào Lãnh địa chiến; chưa xử lý thao tác Mưu kế."""

    step_id = _STEP_QUAN_DOAN_LANH_DIA_CHIEN_MUU_KE
    category_key = "territory_war_tactics"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_LANH_DIA_CHIEN: "territory_war_entry",
    }

    def check(self, context) -> dict:
        return self._match_first({
            **context,
            "template_names": tuple(self.state_by_template),
        })
