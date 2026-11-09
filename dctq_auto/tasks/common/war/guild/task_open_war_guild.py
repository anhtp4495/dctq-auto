"""Mở Chiến Tranh, chuyển trang và vào màn hình Đoàn Chiến."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr, swipe
from dctq_auto.tasks.common.war import task_open_war
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 30


def run(worker, account, device, log) -> bool:
    """Điều hướng vào Đoàn Chiến và xác nhận màn hình đích."""
    if not task_open_war.run(worker, account, device, log):
        return False

    templates = get_templates((
        _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
        _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN,
        _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH,
    ))
    positions = ButtonPositions()
    has_swiped = False

    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang mở Đoàn Chiến.")
            return False
        screen = screen_bgr(device)

        page = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH), account=account, log=log)
        if page is not None:
            log(f"[{account.display_name}] Đã mở màn hình chính Đoàn Chiến.")
            return True

        entry = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN), account=account, log=log)
        if entry is not None:
            x, y = click_match(device, entry)
            log(f"[{account.display_name}] Click lối vào Đoàn Chiến tại ({x}, {y}).")
            time.sleep(1)
            continue

        war_page = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH), account=account, log=log)
        if war_page is not None and not has_swiped:
            start = positions.get("chien_tranh", "item_2")
            end = positions.get("chien_tranh", "item_1")
            swipe(device, start, end, account=account, log=log)
            has_swiped = True
            log(f"[{account.display_name}] Swipe trang Chiến Tranh để tìm lối vào Đoàn Chiến.")
        else:
            log(f"[{account.display_name}] Chưa thấy lối vào Đoàn Chiến (lần {attempt}/{_MAX_TRIES}).")
        time.sleep(1)

    log(f"[{account.display_name}] Không mở được màn hình Đoàn Chiến sau {_MAX_TRIES} lần kiểm tra.")
    return False
