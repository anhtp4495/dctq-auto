"""Mở màn hình và điều hướng vào quy trình Giao Tranh."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import (
    click_match as _click_match,
    match as _match,
    screen_bgr as _screen_bgr,
)


_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)

_MAX_TRIES = 60


def run(
    self,
    account,
    device,
    ocr_client,
    log,
    screenshot=None,
    current_try=1,
) -> bool:
    """Điều hướng vào Giao Tranh bằng cách nhận diện và xử lý từng trạng thái."""
    if current_try == 1:
        log(f"[{account.username}] Bắt đầu mở màn hình Giao Tranh.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.username}] Mở Giao Tranh thất bại: "
            f"quá {_MAX_TRIES} lần kiểm tra."
        )
        return False

    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng khi đang mở Giao Tranh.")
        return False

    try:
        screen = (
            cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
            if screenshot is not None
            else _screen_bgr(device)
        )
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình Giao Tranh: {exc}")
        return False

    templates = get_templates(_OPEN_TEMPLATES)

    # Nhận diện tất cả trạng thái trên cùng một screenshot trước khi xử lý.
    matches = {
        template_name: _match(
            screen,
            templates.get(template_name),
            account=account,
            log=log,
        )
        for template_name in _OPEN_TEMPLATES
    }

    full_open = bool(
        self._config.get("task_open_battle") or self._config.get("xuat_chien")
    )
    find_opponent = bool(self._config.get("task_find_battle_opponent"))
    positions = ButtonPositions()

    # Lối vào Giao Tranh.
    entry = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO]
    if entry is not None:
        x, y = _click_match(device, entry)
        log(f"[{account.username}] Click lối vào Giao Tranh tại ({x}, {y}).")
        time.sleep(1)
        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Khu vực Quân Sự.
    quan_su = matches[_TEMPLATE_MAIN_QUAN_SU]
    if quan_su is not None:
        x, y = _click_match(device, quan_su)
        log(
            f"[{account.username}] Click Quân Sự tại ({x}, {y}); "
            "sẽ tìm lối vào Giao Tranh."
        )
        time.sleep(1)
        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Canh Bát Trận.
    bazhen = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN]
    if self._config.get("task_use_bazhen") and bazhen is not None:
        x, y = _click_match(device, bazhen)
        log(f"[{account.username}] Click sử dụng Canh Bát Trận tại ({x}, {y}).")
        time.sleep(1)

        if not full_open and not find_opponent:
            return True

        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    if not full_open and not find_opponent:
        log(f"[{account.username}] Đã xử lý bước Canh Bát Trận được chọn.")
        return True

    # Tìm đối thủ.
    opponent = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU]
    if opponent is not None:
        x, y = _click_match(device, opponent)
        log(f"[{account.username}] Click Tìm đối thủ tại ({x}, {y}).")
        time.sleep(1)

        if not full_open:
            return True

        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Bài Miễn Chiến.
    immunity = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN]
    if immunity is not None:
        x, y = positions.get(
            "quan_su.giao_tranh", "phat_dong_tan_cong_bo_bai_mien_chien"
        )
        device.shell(f"input tap {x} {y}")
        log(
            f"[{account.username}] Phát hiện Bài Miễn Chiến; "
            f"click phát động giao tranh tại ({x}, {y})."
        )
        time.sleep(1)
        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Cẩm Nang: nhận diện để xác nhận đang ở giao diện Giao Tranh.
    cam_nang = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG]
    if cam_nang is not None:
        log(
            f"[{account.username}] Đã nhận diện Cẩm Nang; "
            "tiếp tục kiểm tra nút Xuất chiến."
        )

    # Chiến Thuật được nhận diện từ chính screenshot hiện tại,
    # không cần chụp hoặc match lại khi đã thấy Xuất chiến.
    strategy_match = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT]

    # Xuất chiến.
    xuat_chien = matches[_TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN]
    if xuat_chien is not None:
        if not full_open:
            log(
                f"[{account.username}] Đã tới giao diện Xuất chiến; "
                "dừng tại đây vì chưa chọn tác vụ mở trận."
            )
            return True

        hero_position_group = (
            "quan_su.giao_tranh.danh_sach1"
            if strategy_match is not None
            else "quan_su.giao_tranh.danh_sach2"
        )
        self._battle_hero_position_group = hero_position_group
        log(
            f"[{account.username}] Chọn bộ tọa độ võ tướng {hero_position_group} "
            f"({'có' if strategy_match is not None else 'không có'} Chiến Thuật)."
        )

        x, y = _click_match(device, xuat_chien)
        log(f"[{account.username}] Click Xuất chiến tại ({x}, {y}); chờ vào trận.")
        time.sleep(1)
        return True

    log(
        f"[{account.username}] Mở Giao Tranh — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); sẽ thử lại."
    )
    time.sleep(1)
    return run(
        self, account, device, ocr_client, log,
        current_try=current_try + 1,
    )
