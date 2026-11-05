"""Mở giao diện và chuẩn bị trận Tranh Bá bằng template matching."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO,
    _TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC,
    _TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN,
    _TEMPLATE_QUAN_SU_TRANH_BA_CHUA_CO_CHIEN_THUAT,
    _TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI,
    _TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN,
    _TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.battle.battle_config import get_battle_config

_MAX_TRIES = 60
_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC,
    _TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN,
    _TEMPLATE_QUAN_SU_TRANH_BA_CHUA_CO_CHIEN_THUAT,
    _TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI,
    _TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN,
    _TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU,
)


def _hero_position_group(screen, templates, account, log):
    """Chọn nhóm tọa độ võ tướng theo trạng thái Chiến thuật."""
    name = _TEMPLATE_QUAN_SU_TRANH_BA_CHUA_CO_CHIEN_THUAT
    template = templates.get(name)
    if template is None:
        return "quan_su.giao_tranh.danh_sach2"
    try:
        found = match_template(
            screen, template.image, threshold=template.threshold,
            method=template.method, search_rect=template.search_rect,
            grayscale=template.grayscale,
        )
    except (ValueError, cv2.error) as exc:
        log(f"[{account.display_name}] Lỗi nhận diện Chiến thuật Tranh Bá: {exc}")
        return "quan_su.giao_tranh.danh_sach2"
    if found is not None:
        report_template_match(log, context=f"[{account.display_name}]", template=template, match=found)
        return "quan_su.giao_tranh.danh_sach2"
    return "quan_su.giao_tranh.danh_sach1"


def run(self, account, device, ocr_client, log, current_try=1) -> bool:
    """Điều hướng đến màn hình Tranh Bá và xác nhận đã vào trận."""
    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu mở màn hình Tranh Bá.")
    if current_try > _MAX_TRIES:
        log(f"[{account.display_name}] Mở Tranh Bá thất bại: quá {_MAX_TRIES} lần kiểm tra.")
        return False
    if not self._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang mở Tranh Bá.")
        return False

    templates = get_templates(_OPEN_TEMPLATES)
    try:
        screen = cv2.cvtColor(np.asarray(device.screenshot()), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình khi mở Tranh Bá: {exc}")
        return False

    positions = ButtonPositions()
    for name in _OPEN_TEMPLATES:
        template = templates.get(name)
        if template is None:
            continue
        try:
            found = match_template(
                screen, template.image, threshold=template.threshold,
                method=template.method, search_rect=template.search_rect,
                grayscale=template.grayscale,
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.display_name}] Lỗi matching {name}: {exc}")
            continue
        if found is None:
            continue

        report_template_match(log, context=f"[{account.display_name}]", template=template, match=found)

        if name == _TEMPLATE_MAIN_QUAN_SU:
            x, y = click_match(device, found)
            time.sleep(1.0)
            log(f"[{account.display_name}] Click Quân Sự tại ({x}, {y}) để mở Tranh Bá.")
        elif name == _TEMPLATE_QUAN_SU_TRANH_BA_LOI_VAO:
            x, y = click_match(device, found)
            time.sleep(1.0)
            log(f"[{account.display_name}] Click Lối vào Tranh Bá tại ({x}, {y}).")
        elif name == _TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC:
            if (
                get_battle_config(self._config).refill
                or self._config.get("task_championship_knb")
                or self._config.get("mua_luot_knb")
            ):
                x, y = positions.get("quan_su.tranh_ba", "xac_nhan_mua_the_luc")
                action = "xác nhận mua thể lực bằng KNB"
            else:
                x, y = positions.get("quan_su.tranh_ba", "huy_mua_the_luc")
                action = "hủy mua thể lực"
            device.shell(f"input tap {x} {y}")
            log(f"[{account.display_name}] Phát hiện hộp thoại mua thể lực; {action} tại ({x}, {y}).")
        elif name == _TEMPLATE_QUAN_SU_TRANH_BA_TIM_DOI_THU:
            x, y = click_match(device, found)
            log(f"[{account.display_name}] Click Tìm đối thủ Tranh Bá tại ({x}, {y}).")
        elif name == _TEMPLATE_QUAN_SU_TRANH_BA_XUAT_CHIEN:
            self._battle_hero_position_group = _hero_position_group(
                screen, templates, account, log
            )
            x, y = click_match(device, found)
            log(
                f"[{account.display_name}] Chọn bộ tọa độ {self._battle_hero_position_group}; "
                f"click Xuất chiến tại ({x}, {y})."
            )
            time.sleep(1)
            return True
        elif name in (
            _TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI,
            _TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN,
            _TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU,
        ):
            log(f"[{account.display_name}] Đã ở trong trận Tranh Bá; chuyển sang theo dõi trận.")
            return True

        time.sleep(0.8)
        return run(self, account, device, ocr_client, log, current_try=current_try + 1)

    log(
        f"[{account.display_name}] Mở Tranh Bá — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(1)
    return run(self, account, device, ocr_client, log, current_try=current_try + 1)
