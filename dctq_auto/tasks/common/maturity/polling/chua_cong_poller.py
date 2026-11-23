"""Poller xử lý category Chúa công trong Trưởng Thành."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MATURITY_CHUA_CONG_CHUA_CHON_CHIEN_KY,
    _TEMPLATE_MATURITY_CHUA_CONG_GIUONG_CO,
    _TEMPLATE_MATURITY_CHUA_CONG_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.maturity.polling.base_poller import BaseMaturityPoller
from dctq_auto.vision.template_store import get_templates


class ChuaCongPoller(BaseMaturityPoller):
    """Nhận diện Chiến kỳ, Giương cờ, thoát và xác nhận màn hình chính."""

    templates = (
        _TEMPLATE_MATURITY_CHUA_CONG_CHUA_CHON_CHIEN_KY,
        _TEMPLATE_MATURITY_CHUA_CONG_GIUONG_CO,
        _TEMPLATE_MATURITY_CHUA_CONG_THOAT,
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
                f"[{account.display_name}] [Trưởng thành] [Chúa công] "
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
            "chua_chon_chien_ky": match(
                screen,
                self.loaded_templates[_TEMPLATE_MATURITY_CHUA_CONG_CHUA_CHON_CHIEN_KY],
                account=account,
                log=context["log"],
            ),
            "giuong_co": match(
                screen,
                self.loaded_templates[_TEMPLATE_MATURITY_CHUA_CONG_GIUONG_CO],
                account=account,
                log=context["log"],
            ),
            "thoat": match(
                screen,
                self.loaded_templates[_TEMPLATE_MATURITY_CHUA_CONG_THOAT],
                account=account,
                log=context["log"],
            ),
        }
