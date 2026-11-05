"""Mở giao diện Chiến Tranh từ màn hình chính."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_CHIEN_TRANH,
    _TEMPLATE_MAIN_QUAN_SU,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 30
_TEMPLATE_NAMES = (
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_MAIN_CHIEN_TRANH,
)


def run(worker, account, device, log) -> bool:
    """Nhận diện màn hình chính, mở Chiến Tranh và xác nhận màn hình đích."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình Chiến Tranh.")
    templates = get_templates(_TEMPLATE_NAMES)

    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang mở Chiến Tranh.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình khi mở Chiến Tranh: {exc}")
            return False

        war_template = templates.get(_TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH)
        war_match = match(screen, war_template, account=account, log=log)
        if war_match is not None:
            log(f"[{account.display_name}] Đã nhận diện màn hình chính Chiến Tranh.")
            return True

        main_template = templates.get(_TEMPLATE_MAIN_QUAN_SU)
        main_match = match(screen, main_template, account=account, log=log)
        if main_match is not None:
            war_entry_template = templates.get(_TEMPLATE_MAIN_CHIEN_TRANH)
            war_entry_match = match(screen, war_entry_template, account=account, log=log)
            if war_entry_match is not None:
                x, y = click_match(device, war_entry_match)
                log(f"[{account.display_name}] Đang ở màn hình chính Quân Sự; click lối vào Chiến Tranh tại ({x}, {y}).")
                time.sleep(1)
                continue

        log(
            f"[{account.display_name}] Mở Chiến Tranh — chưa nhận diện được trạng thái "
            f"(lần {attempt}/{_MAX_TRIES}); thử lại."
        )
        time.sleep(1)

    log(f"[{account.display_name}] Mở Chiến Tranh thất bại sau {_MAX_TRIES} lần kiểm tra.")
    return False
