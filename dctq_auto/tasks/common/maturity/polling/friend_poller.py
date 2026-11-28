"""Poller cho tính năng Bạn Bè, category: ban_be."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MATURITY_BAN_BE_LOI_VAO,
    _TEMPLATE_MATURITY_BAN_BE_MIEN_PHI,
    _TEMPLATE_MATURITY_BAN_BE_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.maturity.polling.base_poller import BaseMaturityPoller
from dctq_auto.vision.template_store import get_templates


class FriendPoller(BaseMaturityPoller):
    """Detects the friends list entry, free heart gift and exit."""

    category_key = "ban_be"
    progress_steps = (
        ("loi_vao", "Lối vào danh sách bạn bè"),
        ("mien_phi", "Tặng tim"),
        ("thoat", "Thoát màn hình Bạn bè"),
    )

    templates = (
        _TEMPLATE_MATURITY_BAN_BE_LOI_VAO,
        _TEMPLATE_MATURITY_BAN_BE_MIEN_PHI,
        _TEMPLATE_MATURITY_BAN_BE_THOAT,
        _TEMPLATE_MAIN_TRUONG_THANH,
    )

    def __init__(self):
        super().__init__()
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
                f"[{account.display_name}] [Trưởng thành] [Friend] "
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
            "ban_be": {
                "loi_vao": (
                    None if self.entry_clicked else match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_BAN_BE_LOI_VAO],
                    account=account,
                    log=context["log"],
                )
                ),
                "mien_phi": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_BAN_BE_MIEN_PHI],
                    account=account,
                    log=context["log"],
                ),
                "thoat": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_BAN_BE_THOAT],
                    account=account,
                    log=context["log"],
                ),
            },
        }
