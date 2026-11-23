"""Polling observation màn hình Trưởng Thành."""

from dctq_auto.config.constants import _TEMPLATE_MAIN_TRUONG_THANH
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.vision.template_store import get_templates


def run(worker, account, device, log) -> dict | None:
    """Thu thập observation cho một chu kỳ polling màn hình Trưởng Thành."""
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi polling màn hình Trưởng Thành.")
        return None

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(
            f"[{account.display_name}] [Trưởng thành] "
            f"Không chụp được màn hình khi polling: {exc}"
        )
        return None

    templates = get_templates((_TEMPLATE_MAIN_TRUONG_THANH,))
    template = templates.get(_TEMPLATE_MAIN_TRUONG_THANH)
    if template is None:
        log(
            f"[{account.display_name}] [Trưởng thành] "
            "Không tải được template màn hình Trưởng Thành."
        )
        return None

    return {
        "screen": screen,
        "templates": templates,
        "main_maturity": match(
            screen,
            template,
            account=account,
            log=log,
        ),
    }
