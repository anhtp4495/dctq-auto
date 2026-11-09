"""Đóng màn hình Đoàn Chiến và xác nhận quay lại menu Chiến Tranh."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_MAN_HINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 15
_TEMPLATES = (
    _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_MAN_HINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
)


def run(worker, account, device, log) -> bool:
    templates = get_templates(_TEMPLATES)
    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang đóng Đoàn Chiến.")
            return False
        screen = screen_bgr(device)

        if match(screen, templates.get(_TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN), account=account, log=log) is not None:
            log(f"[{account.display_name}] Đã đóng Đoàn Chiến và quay lại menu Chiến Tranh.")
            return True
        if match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH), account=account, log=log) is not None:
            log(f"[{account.display_name}] Đã quay lại màn hình chính Chiến Tranh.")
            return True

        summary_close = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET), account=account, log=log)
        if summary_close is not None:
            x, y = click_match(device, summary_close)
            log(f"[{account.display_name}] Đóng bảng tổng kết tại ({x}, {y}).")
        else:
            close = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_MAN_HINH), account=account, log=log)
            if close is not None:
                x, y = click_match(device, close)
                log(f"[{account.display_name}] Đóng màn hình Đoàn Chiến tại ({x}, {y}).")
            else:
                log(f"[{account.display_name}] Chưa thấy nút đóng Đoàn Chiến (lần {attempt}/{_MAX_TRIES}).")
        time.sleep(0.8)

    log(f"[{account.display_name}] Không xác nhận được đã thoát màn hình Đoàn Chiến.")
    return False
