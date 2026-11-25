"""Poller cho tính năng Tướng Ấn, category: tuong_an."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MATURITY_TUONG_AN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_MATURITY_TUONG_AN_LOI_VAO,
    _TEMPLATE_MATURITY_TUONG_AN_TAT_CA,
    _TEMPLATE_MATURITY_TUONG_AN_MIEN_PHI,
    _TEMPLATE_MATURITY_TUONG_AN_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.maturity.polling.base_poller import BaseMaturityPoller
from dctq_auto.vision.template_store import get_templates


class GeneralSealPoller(BaseMaturityPoller):
    """Detects territory exploration, free claim, popup dismissal, and exit."""

    category_key = "tuong_an"
    progress_steps = (
        ("loi_vao", "Thăm dò lãnh địa"),
        ("tat_ca", "Thăm dò tất cả"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Tướng ấn"),
    )

    templates = (
        _TEMPLATE_MATURITY_TUONG_AN_LOI_VAO,
        _TEMPLATE_MATURITY_TUONG_AN_TAT_CA,
        _TEMPLATE_MATURITY_TUONG_AN_MIEN_PHI,
        _TEMPLATE_MATURITY_TUONG_AN_AN_CHO_TRONG_DE_THOAT,
        _TEMPLATE_MATURITY_TUONG_AN_THOAT,
        _TEMPLATE_MAIN_TRUONG_THANH,
    )

    def __init__(self):
        super().__init__()
        self.loaded_templates = get_templates(self.templates)
        missing = [
            name for name in self.templates
            if self.loaded_templates.get(name) is None
        ]
        if missing:
            raise ValueError(f"Thiếu template: {', '.join(missing)}")

    def check(self, context) -> dict | None:
        account = context["account"]
        try:
            screen = screen_bgr(context["device"])
        except Exception as exc:
            context["log"](
                f"[{account.display_name}] [Trưởng thành] [General Seal] "
                f"Failed to capture screen: {exc}"
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
            "tuong_an": {
                "loi_vao": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_TUONG_AN_LOI_VAO],
                    account=account,
                    log=context["log"],
                ),
                "tat_ca": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_TUONG_AN_TAT_CA],
                    account=account,
                    log=context["log"],
                ),
                "mien_phi": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_TUONG_AN_MIEN_PHI],
                    account=account,
                    log=context["log"],
                ),
                "an_cho_trong_de_thoat": match(
                    screen,
                    self.loaded_templates[
                        _TEMPLATE_MATURITY_TUONG_AN_AN_CHO_TRONG_DE_THOAT
                    ],
                    account=account,
                    log=context["log"],
                ),
                "thoat": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_TUONG_AN_THOAT],
                    account=account,
                    log=context["log"],
                ),
            },
        }
