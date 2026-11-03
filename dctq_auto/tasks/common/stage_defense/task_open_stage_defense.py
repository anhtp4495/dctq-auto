"""Mở giao diện và điều hướng vào Mưu Binh bằng template matching."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MUU_BINH,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_XUAT_CHIEN,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.tasks.common.battle.battle_utils import click_match, swipe


_MAX_TRIES = 60
_OPEN_TEMPLATES = (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MUU_BINH,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO,
    _TEMPLATE_MUU_BINH_XUAT_CHIEN,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
)


def run(self, account, device, ocr_client, log, current_try=1, has_swiped_war_menu=False) -> bool:
    """Điều hướng vào màn hình Mưu Binh; vòng vượt ải do task_run_stage_defense xử lý."""
    if current_try == 1:
        log(f"[{account.username}] Bắt đầu mở màn hình Mưu Binh.")
    if current_try > _MAX_TRIES:
        log(f"[{account.username}] Vào Mưu Binh thất bại: quá {_MAX_TRIES} lần kiểm tra.")
        return False
    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang mở Mưu Binh.")
        return False

    templates = get_templates(_OPEN_TEMPLATES)
    try:
        screen = cv2.cvtColor(np.asarray(device.screenshot()), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình khi mở Mưu Binh: {exc}")
        return False

    positions = ButtonPositions()
    for name in _OPEN_TEMPLATES:
        template = templates.get(name)
        if template is None:
            continue
        try:
            found = match_template(
                screen,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=template.search_rect,
                grayscale=template.grayscale,
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.username}] Lỗi matching template {name}: {exc}")
            continue
        if found is None:
            continue

        report_template_match(
            log,
            context=f"[{account.username}]",
            template=template,
            match=found,
        )

        if name == _TEMPLATE_MAIN_QUAN_SU:
            x, y = click_match(device, found)
            log(f"[{account.username}] Click Quân Sự tại ({x}, {y}) để mở Chiến Tranh.")
        elif name == _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH:
            if has_swiped_war_menu:
                try:
                    x, y = positions.get("chien_tranh", "dong_man_hinh")
                    device.shell(f"input tap {x} {y}")
                    log(
                        f"[{account.username}] Đã swipe nhưng vẫn ở màn hình Chiến Tranh; "
                        f"đóng màn hình tại ({x}, {y}). Vào Mưu Binh thất bại."
                    )
                except (KeyError, ValueError) as exc:
                    log(
                        f"[{account.username}] Không lấy được tọa độ đóng màn hình Chiến Tranh: "
                        f"{exc}. Vào Mưu Binh thất bại."
                    )
                return False

            start = positions.get("chien_tranh", "item_2")
            end = positions.get("chien_tranh", "item_1")
            swipe(device, start, end, account=account, log=log)
            has_swiped_war_menu = True
            log(f"[{account.username}] Swipe màn hình Chiến Tranh từ item_2 sang item_1.")
        elif name == _TEMPLATE_CHIEN_TRANH_MUU_BINH:
            x, y = click_match(device, found)
            log(f"[{account.username}] Click Mưu Binh tại ({x}, {y}).")
        elif name == _TEMPLATE_MUU_BINH_CHIEN_DAU:
            x, y = click_match(device, found)
            log(f"[{account.username}] Click Chiến đấu tại ({x}, {y}).")
        elif name == _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO:
            x, y = click_match(device, found)
            log(f"[{account.username}] Click Tự động đến ải tiếp theo tại ({x}, {y}).")
        elif name in (
            _TEMPLATE_MUU_BINH_XUAT_CHIEN,
            _TEMPLATE_MUU_BINH_HOI_THANH,
            _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
        ):
            log(f"[{account.username}] Đã mở Mưu Binh thành công; chuyển sang tự động vượt ải.")
            return True

        time.sleep(1)
        return run(
            self,
            account,
            device,
            ocr_client,
            log,
            current_try=current_try + 1,
            has_swiped_war_menu=has_swiped_war_menu,
        )

    log(
        f"[{account.username}] Mở Mưu Binh — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(1)
    return run(
        self,
        account,
        device,
        ocr_client,
        log,
        current_try=current_try + 1,
        has_swiped_war_menu=has_swiped_war_menu,
    )
