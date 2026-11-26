"""Poller khung cho tác vụ Bổ sung phòng thủ Đoàn Chiến."""

from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU
from dctq_auto.tasks.common.guild.polling.base_poller import BaseGuildPoller


class DefenseReinforcementPoller(BaseGuildPoller):
    """Khung nhận diện; sẽ bổ sung danh sách template khi có dữ liệu template."""

    step_id = _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU
    category_key = "guild_war_defense_reinforcement"
    state_by_template = {}
    template_names = ()

    def check(self, context) -> dict:
        return self._match_first({**context, "template_names": self.template_names})
