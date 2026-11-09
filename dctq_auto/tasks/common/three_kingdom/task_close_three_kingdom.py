"""Đóng màn hình Tam Quốc Lệnh và xác nhận quay lại màn hình Quân Sự."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_TAM_QUOC_LENH_DONG_MAN_HINH_CHINH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 20
_POLL_INTERVAL = 0.8
_CLOSE_TEMPLATES = (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_TAM_QUOC_LENH_DONG_MAN_HINH_CHINH,
)


def run(worker, account, device, log, current_try=1) -> bool:
    """Đóng Tam Quốc Lệnh; trả về True khi đã về màn hình Quân Sự."""

    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu đóng màn hình Tam Quốc Lệnh.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.display_name}] Không xác nhận được đã đóng "
            f"Tam Quốc Lệnh sau {_MAX_TRIES} lần kiểm tra."
        )
        return False

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang đóng Tam Quốc Lệnh.")
        return False

    templates = get_templates(_CLOSE_TEMPLATES)

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(
            f"[{account.display_name}] Không chụp được màn hình "
            f"khi đóng Tam Quốc Lệnh: {exc}"
        )
        return False

    for template_name in _CLOSE_TEMPLATES:
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

        if template_name == _TEMPLATE_MAIN_QUAN_SU:
            log(
                f"[{account.display_name}] Đã đóng Tam Quốc Lệnh, "
                "quay lại màn hình Quân Sự."
            )
            return True

        try:
            x, y = click_match(device, found)
            log(
                f"[{account.display_name}] Click đóng màn hình Tam Quốc Lệnh "
                f"tại ({x}, {y})."
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] Không click được nút đóng "
                f"Tam Quốc Lệnh: {exc}"
            )
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
        f"[{account.display_name}] Chưa nhận diện được trạng thái đóng "
        f"Tam Quốc Lệnh (lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(_POLL_INTERVAL)
    return run(
        worker,
        account,
        device,
        log,
        current_try=current_try + 1,
    )
