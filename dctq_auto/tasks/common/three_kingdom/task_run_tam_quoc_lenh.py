"""Thực hiện nhận thưởng nhanh trong giao diện Tam Quốc Lệnh."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 10
_REWARD_TEMPLATES = (
    _TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
)


def run(worker, account, device, log) -> bool:
    """Mở tab chưa nhận, nhấn nhận nhanh và xác nhận trạng thái đã nhận."""
    log(f"[{account.display_name}] Bắt đầu nhận thưởng Tam Quốc Lệnh.")
    templates = get_templates(_REWARD_TEMPLATES)

    for current_try in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang nhận thưởng Tam Quốc Lệnh.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình nhận thưởng: {exc}")
            return False

        unopened_tab = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG),
            account=account,
            log=log,
        )
        if unopened_tab is not None:
            try:
                x, y = click_match(device, unopened_tab)
                log(f"[{account.display_name}] Click tab chưa nhận thưởng tại ({x}, {y}).")
            except Exception as exc:
                log(f"[{account.display_name}] Không mở được tab chưa nhận thưởng: {exc}")
                return False
            time.sleep(0.7)
            continue

        quick_reward = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH),
            account=account,
            log=log,
        )
        if quick_reward is not None:
            try:
                x, y = click_match(device, quick_reward)
                log(f"[{account.display_name}] Click nhận thưởng nhanh tại ({x}, {y}).")
            except Exception as exc:
                log(f"[{account.display_name}] Không click được nhận thưởng nhanh: {exc}")
                return False
            time.sleep(0.8)
            continue

        claimed_tab = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG),
            account=account,
            log=log,
        )
        if claimed_tab is not None:
            log(f"[{account.display_name}] Đã xác nhận trạng thái nhận thưởng Tam Quốc Lệnh.")
            return True

        log(
            f"[{account.display_name}] Chưa nhận diện được trạng thái nhận thưởng "
            f"(lần {current_try}/{_MAX_TRIES}); thử lại."
        )
        time.sleep(0.8)

    log(f"[{account.display_name}] Không xác nhận được hoàn tất nhận thưởng Tam Quốc Lệnh.")
    return False
