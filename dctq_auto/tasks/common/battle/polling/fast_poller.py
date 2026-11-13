"""Poller cho chế độ Giao Tranh nhanh 1 cờ."""

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import match

from .base_poller import BasePoller


class FastPoller(BasePoller):
    """Kết thúc lượt khi nhận diện được trạng thái 1 cờ hoặc 2 cờ."""

    templates = BasePoller.templates + (
        _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
    )

    def check(self, context) -> dict | None:
        observation = super().check(context)
        if observation is None:
            return None
        account = context["account"]
        templates = observation["templates"]

        context["log"](f"[{account.display_name}] Chế độ nhanh 1 cờ -> ")

        for template_name in (
            _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
            _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
        ):
            found = match(
                observation["screen"], templates.get(template_name),
                account=account, log=context["log"],
            )
            if found is not None:
                context["log"](
                    f"[{account.display_name}] Chế độ nhanh 1 cờ: đã phát hiện "
                    f"{template_name.rsplit('/', 1)[-1]}."
                )
                observation["should_end"] = True
                observation["end_reason"] = template_name
                break
        return observation
