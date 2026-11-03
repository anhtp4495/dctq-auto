"""Đóng giao diện Chiến Tranh và xác nhận trở về màn hình chính."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_QUAN_SU,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 20
_TEMPLATE_NAMES = (
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_QUAN_SU,
)


def run(worker, account, device, log) -> bool:
    """Click nút đóng Chiến Tranh theo button_positions rồi xác nhận màn hình chính."""
    log(f"[{account.username}] Bắt đầu đóng màn hình Chiến Tranh.")
    templates = get_templates(_TEMPLATE_NAMES)
    positions = ButtonPositions()
    close_clicked = False

    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang đóng Chiến Tranh.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình khi đóng Chiến Tranh: {exc}")
            return False

        main_match = match(screen, templates.get(_TEMPLATE_MAIN_QUAN_SU), account=account, log=log)
        if main_match is not None:
            log(f"[{account.username}] Đã xác nhận trở về màn hình chính Quân Sự.")
            return True

        war_match = match(
            screen,
            templates.get(_TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH),
            account=account,
            log=log,
        )
        if war_match is not None and not close_clicked:
            x, y = positions.get("chien_tranh", "dong_man_hinh")
            device.shell(f"input tap {x} {y}")
            log(f"[{account.username}] Click đóng màn hình Chiến Tranh tại ({x}, {y}).")
            close_clicked = True
            time.sleep(1)
            continue

        log(
            f"[{account.username}] Đóng Chiến Tranh — đang chờ xác nhận màn hình chính "
            f"(lần {attempt}/{_MAX_TRIES})."
        )
        time.sleep(1)

    log(f"[{account.username}] Không xác nhận được đã đóng màn hình Chiến Tranh.")
    return False
