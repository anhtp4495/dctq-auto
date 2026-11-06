"""Điều hướng vào giao diện Tam Quốc Lệnh bằng template matching."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
    _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 20
_OPEN_TEMPLATES = (
    _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
)


def run(worker, account, device, ocr_client, log) -> bool:
    """Mở Tam Quốc Lệnh; trả về True khi nhận diện được màn hình đích."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình Tam Quốc Lệnh.")
    templates = get_templates(_OPEN_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang mở Tam Quốc Lệnh.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình khi mở Tam Quốc Lệnh: {exc}")
            return False

        page_match = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH),
            account=account,
            log=log,
        )
        if page_match is not None:
            log(f"[{account.display_name}] Đã mở màn hình Tam Quốc Lệnh.")
            return True

        entry_match = match(
            screen,
            templates.get(_TEMPLATE_MAIN_TAM_QUOC_LENH),
            account=account,
            log=log,
        )
        if entry_match is not None:
            try:
                x, y = click_match(device, entry_match)
                log(f"[{account.display_name}] Click lối vào Tam Quốc Lệnh tại ({x}, {y}).")
            except Exception as exc:
                log(f"[{account.display_name}] Không click được lối vào Tam Quốc Lệnh: {exc}")
                return False
        else:
            log(
                f"[{account.display_name}] Chưa nhận diện được lối vào hoặc màn hình "
                f"Tam Quốc Lệnh (lần {current_try}/{_MAX_TRIES}); thử lại."
            )

        time.sleep(1)

    log(f"[{account.display_name}] Mở Tam Quốc Lệnh thất bại sau {_MAX_TRIES} lần kiểm tra.")
    return False
