"""Mở giao diện Chiến Tranh và điều hướng vào màn hình Đoàn Chiến."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_QUAN_SU,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, swipe
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match


_MAX_TRIES = 60
_OPEN_TEMPLATES = (
    _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_QUAN_SU,
)


def run(worker, account, device, log, current_try=1, has_swiped_war_menu=False) -> bool:
    """Điều hướng vào màn hình chính Đoàn Chiến."""
    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu mở màn hình Đoàn Chiến.")
    if current_try > _MAX_TRIES:
        log(f"[{account.display_name}] Vào Đoàn Chiến thất bại: quá {_MAX_TRIES} lần kiểm tra.")
        return False
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang mở Đoàn Chiến.")
        return False

    templates = get_templates(_OPEN_TEMPLATES)
    try:
        screen = cv2.cvtColor(np.asarray(device.screenshot()), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình khi mở Đoàn Chiến: {exc}")
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
            log(f"[{account.display_name}] Lỗi matching template {name}: {exc}")
            continue
        if found is None:
            continue

        report_template_match(
            log,
            context=f"[{account.display_name}]",
            template=template,
            match=found,
        )

        if name == _TEMPLATE_MAIN_QUAN_SU:
            from dctq_auto.tasks.common.war import task_open_war

            if not task_open_war.run(worker, account, device, log):
                log(f"[{account.display_name}] Không mở được Chiến Tranh; dừng mở Đoàn Chiến.")
                return False
            log(f"[{account.display_name}] Đã mở Chiến Tranh; tiếp tục nhận diện để mở Đoàn Chiến.")
            time.sleep(1)
            return run(
                worker,
                account,
                device,
                log,
                current_try=current_try + 1,
                has_swiped_war_menu=False,
            )
        elif name == _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH:
            if has_swiped_war_menu:
                try:
                    x, y = positions.get("chien_tranh", "dong_man_hinh")
                    device.shell(f"input tap {x} {y}")
                    log(
                        f"[{account.display_name}] Đã swipe nhưng vẫn ở màn hình Chiến Tranh; "
                        f"đóng màn hình tại ({x}, {y}). Vào Đoàn Chiến thất bại."
                    )
                except (KeyError, ValueError) as exc:
                    log(
                        f"[{account.display_name}] Không lấy được tọa độ đóng màn hình Chiến Tranh: "
                        f"{exc}. Vào Đoàn Chiến thất bại."
                    )
                return False

            start = positions.get("chien_tranh", "item_2")
            end = positions.get("chien_tranh", "item_1")
            swipe(device, start, end, account=account, log=log)
            has_swiped_war_menu = True
            log(f"[{account.display_name}] Swipe màn hình Chiến Tranh từ item_2 sang item_1.")
        elif name == _TEMPLATE_CHIEN_TRANH2_DOAN_CHIEN:
            x, y = click_match(device, found)
            log(f"[{account.display_name}] Click lối vào Đoàn Chiến tại ({x}, {y}).")
        elif name == _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_MAN_HINH_CHINH:
            log(f"[{account.display_name}] Đã mở màn hình chính Đoàn Chiến.")
            return True

        time.sleep(1)
        return run(
            worker,
            account,
            device,
            log,
            current_try=current_try + 1,
            has_swiped_war_menu=has_swiped_war_menu,
        )

    log(
        f"[{account.display_name}] Mở Đoàn Chiến — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(1)
    return run(
        worker,
        account,
        device,
        log,
        current_try=current_try + 1,
        has_swiped_war_menu=has_swiped_war_menu,
    )
