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
_POLL_INTERVAL = 0.8
_TEMPLATES = (
    _TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
)


def run(worker, account, device, log, current_try=1) -> bool:
    """Mở tab chưa nhận, nhấn nhận nhanh và xác nhận trạng thái đã nhận."""

    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu nhận thưởng Tam Quốc Lệnh.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.display_name}] Không xác nhận được hoàn tất nhận thưởng "
            f"Tam Quốc Lệnh sau {_MAX_TRIES} lần."
        )
        return False

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang nhận thưởng Tam Quốc Lệnh.")
        return False

    templates = get_templates(_TEMPLATES)

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình nhận thưởng: {exc}")
        return False

    for template_name in _TEMPLATES:
        template = templates.get(template_name)
        if template is None:
            log(
                f"[{account.display_name}] Không tải được template "
                f"{template_name}; bỏ qua."
            )
            continue

        match_template = match(screen, template, account=account, log=log)
        if match_template is None:
            continue

        if template_name == _TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG:
            log(f"[{account.display_name}] Đã xác nhận trạng thái nhận thưởng Tam Quốc Lệnh.")
            return True

        try:
            x, y = click_match(device, match_template)
            action = (
                "tab chưa nhận thưởng"
                if template_name == _TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG
                else "nhận thưởng nhanh"
            )
            log(f"[{account.display_name}] Click {action} tại ({x}, {y}).")
        except Exception as exc:
            log(f"[{account.display_name}] Không click được [{template_name}]: {exc}")
            return False

        time.sleep(_POLL_INTERVAL)
        return run(
            worker,
            account,
            device,
            log,
            current_try=current_try + 1,
        )

    log(
        f"[{account.display_name}] Chưa nhận diện được trạng thái nhận thưởng "
        f"(lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(_POLL_INTERVAL)
    return run(
        worker,
        account,
        device,
        log,
        current_try=current_try + 1,
    )
