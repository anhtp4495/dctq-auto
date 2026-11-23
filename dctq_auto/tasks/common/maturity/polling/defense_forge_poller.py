"""Poller cho tính năng Thần Tượng, category: than_tuong."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MATURITY_THAN_TUONG_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_MATURITY_THAN_TUONG_LOI_VAO,
    _TEMPLATE_MATURITY_THAN_TUONG_MIEN_PHI,
    _TEMPLATE_MATURITY_THAN_TUONG_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.maturity.polling.base_poller import BaseMaturityPoller
from dctq_auto.vision.template_store import get_templates


class DefenseForgePoller(BaseMaturityPoller):
    """Detects the Defense Forge entry, free action, popup dismissal and exit."""

    templates = (
        _TEMPLATE_MATURITY_THAN_TUONG_LOI_VAO,
        _TEMPLATE_MATURITY_THAN_TUONG_MIEN_PHI,
        _TEMPLATE_MATURITY_THAN_TUONG_AN_CHO_TRONG_DE_THOAT,
        _TEMPLATE_MATURITY_THAN_TUONG_THOAT,
        _TEMPLATE_MAIN_TRUONG_THANH,
    )

    def __init__(self):
        self.loaded_templates = get_templates(self.templates)
        missing = [
            name for name in self.templates
            if self.loaded_templates.get(name) is None
        ]
        if missing:
            raise ValueError(f"Thiếu template: {', '.join(missing)}")
        self.waiting_for_main = False

    def check(self, context) -> dict | None:
        account = context["account"]
        try:
            screen = screen_bgr(context["device"])
        except Exception as exc:
            context["log"](
                f"[{account.display_name}] [Trưởng thành] [Defense Forge] "
                f"Không chụp được màn hình: {exc}"
            )
            return None

        if self.waiting_for_main:
            return {
                "screen": screen,
                "main_maturity": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MAIN_TRUONG_THANH],
                    account=account,
                    log=context["log"],
                ),
            }

        return {
            "screen": screen,
            "than_tuong": {
                "loi_vao": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_THAN_TUONG_LOI_VAO],
                    account=account,
                    log=context["log"],
                ),
                "mien_phi": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_THAN_TUONG_MIEN_PHI],
                    account=account,
                    log=context["log"],
                ),
                "an_cho_trong_de_thoat": match(
                    screen,
                    self.loaded_templates[
                        _TEMPLATE_MATURITY_THAN_TUONG_AN_CHO_TRONG_DE_THOAT
                    ],
                    account=account,
                    log=context["log"],
                ),
                "thoat": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_THAN_TUONG_THOAT],
                    account=account,
                    log=context["log"],
                ),
            },
        }
