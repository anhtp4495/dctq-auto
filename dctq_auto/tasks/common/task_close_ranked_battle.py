"""Đóng giao diện Tranh Bá và trở về màn hình chính."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH,
    _TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO,
    _TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr

_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH,
    _TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN,
)
_MAX_TRIES = 60


def run(self, account, device, ocr_client, log, current_try=1) -> bool:
    """Nhận diện trạng thái rồi đóng Tranh Bá theo tọa độ đã cấu hình."""
    if current_try == 1:
        log(f"[{account.username}] Bắt đầu đóng màn hình Tranh Bá.")
    if current_try > _MAX_TRIES:
        log(f"[{account.username}] Đóng Tranh Bá thất bại: quá {_MAX_TRIES} lần kiểm tra.")
        return False
    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang đóng Tranh Bá.")
        return False

    templates = get_templates(_CLOSE_TEMPLATES)
    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để đóng Tranh Bá: {exc}")
        return False

    positions = ButtonPositions()
    for name in _CLOSE_TEMPLATES:
        found = match(screen, templates.get(name), account=account, log=log)
        if found is None:
            continue
        if name == _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH:
            x, y = click_match(device, found)
            log(f"[{account.username}] Click Hồi thành Tranh Bá tại ({x}, {y}).")
            time.sleep(1)
            return run(self, account, device, ocr_client, log, current_try + 1)
        if name == _TEMPLATE_MAIN_QUAN_SU:
            log(f"[{account.username}] Đã trở về màn hình chính Quân Sự.")
            return True
        if name in (
            _TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO,
            _TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU,
            _TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN,
        ):
            x, y = positions.get("quan_su.tranh_ba", "dong_man_hanh")
            device.shell(f"input tap {x} {y}")
            log(f"[{account.username}] Đóng giao diện Tranh Bá tại ({x}, {y}).")
            time.sleep(1)
            return run(self, account, device, ocr_client, log, current_try + 1)

    log(
        f"[{account.username}] Đóng Tranh Bá — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(1)
    return run(self, account, device, ocr_client, log, current_try + 1)
