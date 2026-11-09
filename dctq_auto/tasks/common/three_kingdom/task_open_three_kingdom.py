"""Điều hướng vào giao diện Tam Quốc Lệnh bằng template matching."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
    _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_CHUA_NHAN_TAM_QUOC_LENH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 3
_POLL_INTERVAL = 1
_OPEN_TEMPLATES = (
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
    _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_CHUA_NHAN_TAM_QUOC_LENH,
)


def run(worker, account, device, ocr_client, log, current_try=1) -> bool:
    """Mở Tam Quốc Lệnh; trả về True khi nhận diện được màn hình đích."""

    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu mở màn hình Tam Quốc Lệnh.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.display_name}] Mở Tam Quốc Lệnh thất bại "
            f"sau {_MAX_TRIES} lần kiểm tra."
        )
        return False

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang mở Tam Quốc Lệnh.")
        return False

    templates = get_templates(_OPEN_TEMPLATES)

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(
            f"[{account.display_name}] Không chụp được màn hình "
            f"khi mở Tam Quốc Lệnh: {exc}"
        )
        return False

    for template_name in _OPEN_TEMPLATES:
        template = templates.get(template_name)
        if template is None:
            log(
                f"[{account.display_name}] Không tải được template "
                f"{template_name}; bỏ qua."
            )
            continue

        found = match(screen, template, account=account, log=log)
        if found is None:
            continue

        if template_name == _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH:
            log(f"[{account.display_name}] Đã mở màn hình Tam Quốc Lệnh.")
            return True

        try:
            x, y = click_match(device, found)
            log(
                f"[{account.display_name}] Click lối vào Tam Quốc Lệnh "
                f"tại ({x}, {y})."
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] Không click được lối vào "
                f"Tam Quốc Lệnh: {exc}"
            )
            return False

        time.sleep(_POLL_INTERVAL)
        return run(
            worker,
            account,
            device,
            ocr_client,
            log,
            current_try=current_try + 1,
        )

    log(
        f"[{account.display_name}] Chưa nhận diện được trạng thái "
        f"Tam Quốc Lệnh (lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(_POLL_INTERVAL)
    return run(
        worker,
        account,
        device,
        ocr_client,
        log,
        current_try=current_try + 1,
    )
