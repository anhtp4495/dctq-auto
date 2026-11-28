"""Poller cho tính năng Chiến Hồn, category: chien_hon."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MATURITY_CHIEN_HON_BI_BAO,
    _TEMPLATE_MATURITY_CHIEN_HON_LOI_VAO,
    _TEMPLATE_MATURITY_CHIEN_HON_MIEN_PHI,
    _TEMPLATE_MATURITY_CHIEN_HON_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.maturity.polling.base_poller import BaseMaturityPoller
from dctq_auto.vision.template_store import get_templates


class SoulPoller(BaseMaturityPoller):
    """Nhận diện lối vào, miễn phí, thoát popup và thoát màn hình Chiến hồn."""

    category_key = "chien_hon"
    progress_steps = (
        ("chien_hon_bi_bao", "Nhận Chiến hồn"),
        ("loi_vao", "Lối vào Chiến hồn"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Chiến hồn"),
    )

    templates = (
        _TEMPLATE_MATURITY_CHIEN_HON_BI_BAO,
        _TEMPLATE_MATURITY_CHIEN_HON_LOI_VAO,
        _TEMPLATE_MATURITY_CHIEN_HON_MIEN_PHI,
        _TEMPLATE_MATURITY_CHIEN_HON_THOAT,
        _TEMPLATE_MAIN_TRUONG_THANH,
    )

    def __init__(self):
        super().__init__()
        self.bi_bao_clicked = False
        self.entry_clicked = False
        self.waiting_for_exit = False
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
                f"[{account.display_name}] [Trưởng thành] [Chiến hồn] "
                f"Không chụp được màn hình: {exc}"
            )
            return None

        if self.waiting_for_exit:
            thoat = match(
                screen,
                self.loaded_templates[_TEMPLATE_MATURITY_CHIEN_HON_THOAT],
                account=account,
                log=context["log"],
            )
            if thoat is not None:
                return {"screen": screen, "chien_hon": {"thoat": thoat}}
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

        if not self.bi_bao_clicked:
            return {
                "screen": screen,
                "chien_hon": {
                    "loi_vao": match(
                        screen,
                        self.loaded_templates[_TEMPLATE_MATURITY_CHIEN_HON_LOI_VAO],
                        account=account,
                        log=context["log"],
                    ),
                    "chien_hon_bi_bao": match(
                        screen,
                        self.loaded_templates[_TEMPLATE_MATURITY_CHIEN_HON_BI_BAO],
                        account=account,
                        log=context["log"],
                    )
                },
            }

        if not self.entry_clicked:
            return {
                "screen": screen,
                "chien_hon": {
                    "loi_vao": match(
                        screen,
                        self.loaded_templates[_TEMPLATE_MATURITY_CHIEN_HON_LOI_VAO],
                        account=account,
                        log=context["log"],
                    ),
                },
            }

        return {
            "screen": screen,
            "chien_hon": {
                "loi_vao": None,
                "mien_phi": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_CHIEN_HON_MIEN_PHI],
                    account=account,
                    log=context["log"],
                ),
                "thoat": match(
                    screen,
                    self.loaded_templates[_TEMPLATE_MATURITY_CHIEN_HON_THOAT],
                    account=account,
                    log=context["log"],
                ),
            },
        }
