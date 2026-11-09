"""Đóng màn hình Đoàn Chiến và xác nhận quay lại màn hình Quân Sự."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_MAN_HINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DONG_TONG_KET,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 15
_POLL_INTERVAL = 0.8
_CLOSE_TEMPLATES = (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_MAN_HINH,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DONG_TONG_KET,
)


def run(worker, account, device, log) -> bool:
    """Đóng lần lượt các lớp màn hình và xác nhận đã về màn hình Quân Sự."""

    templates = get_templates(_CLOSE_TEMPLATES)

    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang đóng Đoàn Chiến.")
            return False

        clicked = False
        for template_name in _CLOSE_TEMPLATES:
            template = templates.get(template_name)
            if template is None:
                log(
                    f"[{account.display_name}] Không tải được template "
                    f"{template_name}; bỏ qua."
                )
                continue

            screen = screen_bgr(device)
            match_template = match(screen, template, account=account, log=log)
            if match_template is None:
                continue

            if template_name == _TEMPLATE_MAIN_QUAN_SU:
                log(
                    f"[{account.display_name}] Đã đóng Đoàn Chiến và quay lại "
                    "màn hình Quân Sự."
                )
                return True

            x, y = click_match(device, match_template)
            log(
                f"[{account.display_name}] Click [{template_name}] "
                f"để đóng Đoàn Chiến tại ({x}, {y})."
            )
            clicked = True
            break

        if not clicked:
            log(
                f"[{account.display_name}] Chưa tìm thấy nút đóng Đoàn Chiến "
                f"(lần {attempt}/{_MAX_TRIES})."
            )

        time.sleep(_POLL_INTERVAL)

    log(
        f"[{account.display_name}] Không xác nhận được đã quay lại "
        "màn hình Quân Sự sau khi đóng Đoàn Chiến."
    )
    return False
