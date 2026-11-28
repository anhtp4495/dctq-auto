"""Poller cho tính năng Vệ Tướng, category: ve_tuong."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MATURITY_VE_TUONG_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_MATURITY_VE_TUONG_LOI_VAO,
    _TEMPLATE_MATURITY_VE_TUONG_MIEN_PHI,
    _TEMPLATE_MATURITY_VE_TUONG_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.maturity.polling.base_poller import BaseMaturityPoller
from dctq_auto.vision.template_store import get_templates


class GuardianPoller(BaseMaturityPoller):
    """Nhận diện lối vào, miễn phí, thoát popup và thoát màn hình Vệ tướng."""

    category_key = "ve_tuong"
    progress_steps = (
        ("loi_vao", "Lối vào Vệ tướng"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Vệ tướng"),
    )

    templates = (
        _TEMPLATE_MATURITY_VE_TUONG_LOI_VAO,
        _TEMPLATE_MATURITY_VE_TUONG_MIEN_PHI,
        _TEMPLATE_MATURITY_VE_TUONG_AN_CHO_TRONG_DE_THOAT,
        _TEMPLATE_MATURITY_VE_TUONG_THOAT,
        _TEMPLATE_MAIN_TRUONG_THANH,
    )

    def __init__(self):
        super().__init__()
        self.waiting_for_exit = False
        self.entry_clicked = False
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
                f"[{account.display_name}] [Trưởng thành] [Vệ tướng] "
                f"Không chụp được màn hình: {exc}"
            )
            return None

        if self.waiting_for_exit:
            thoat = match(
                screen,
                self.loaded_templates[_TEMPLATE_MATURITY_VE_TUONG_THOAT],
                account=account,
                log=context["log"],
            )
            if thoat is not None:
                return {"screen": screen, "ve_tuong": {"thoat": thoat}}
            return {"screen": screen, "exit_closed": True}

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
            "ve_tuong": {
                "loi_vao": (
                    None if self.entry_clicked else match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_VE_TUONG_LOI_VAO],
                    account=account,
                    log=context["log"],
                )
                ),
                "mien_phi": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_VE_TUONG_MIEN_PHI],
                    account=account,
                    log=context["log"],
                ),
                "an_cho_trong_de_thoat": match(
                    screen,
                    self.loaded_templates[
                        _TEMPLATE_MATURITY_VE_TUONG_AN_CHO_TRONG_DE_THOAT
                    ],
                    account=account,
                    log=context["log"],
                ),
                "thoat": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_VE_TUONG_THOAT],
                    account=account,
                    log=context["log"],
                ),
            },
        }
