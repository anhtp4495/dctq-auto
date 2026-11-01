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
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)


def task_open_battle(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Điều hướng vào Giao Tranh, chọn bộ tọa độ và click Xuất chiến."""
    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng trước khi mở Giao Tranh.")
        return False

    log(f"[{account.username}] Bắt đầu mở màn hình Giao Tranh.")
    templates = get_templates(_OPEN_TEMPLATES)
    positions = ButtonPositions()
    max_attempts = 60
    full_open = bool(self._config.get("task_open_battle") or self._config.get("xuat_chien"))

    for attempt in range(1, max_attempts + 1):
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang mở Giao Tranh.")
            return False
        try:
            screen = (
                cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
                if screenshot is not None else _screen_bgr(device)
            )
            screenshot = None
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình Giao Tranh: {exc}")
            return False

        # Bước 1: đang ở màn hình chính Quân Sự thì mở lối vào Giao Tranh.
        entry = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO),
            account=account, log=log,
        )
        if entry is not None:
            x, y = _click_match(device, entry)
            log(f"[{account.username}] Click lối vào Giao Tranh tại ({x}, {y}).")
            time.sleep(1)
            continue

        # Bước 2: nếu chưa thấy lối vào, mở mục Quân Sự rồi nhận diện lại.
        quan_su = _match(
            screen, templates.get(_TEMPLATE_MAIN_QUAN_SU),
            account=account, log=log,
        )
        if quan_su is not None:
            x, y = _click_match(device, quan_su)
            log(f"[{account.username}] Click Quân Sự tại ({x}, {y}); sẽ tìm lối vào Giao Tranh.")
            time.sleep(1)
            continue

        # Bước 3: chỉ dùng Canh Bát Trận khi người dùng bật tác vụ tương ứng.
        if self._config.get("task_use_bazhen"):
            bazhen = _match(
                screen,
                templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN),
                account=account, log=log,
            )
            if bazhen is not None:
                x, y = _click_match(device, bazhen)
                log(f"[{account.username}] Click sử dụng Canh Bát Trận tại ({x}, {y}).")
                time.sleep(1)
                if not full_open and not self._config.get("task_find_battle_opponent"):
                    return True
                continue

        if not full_open and not self._config.get("task_find_battle_opponent"):
            # Nếu không yêu cầu mở tiếp quy trình, không tự ý tìm đối thủ.
            log(f"[{account.username}] Đã xử lý bước Canh Bát Trận được chọn.")
            return True

        # Bước 4: mở giao diện tìm đối thủ.
        opponent = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU),
            account=account, log=log,
        )
        if opponent is not None:
            x, y = _click_match(device, opponent)
            log(f"[{account.username}] Click Tìm đối thủ tại ({x}, {y}).")
            time.sleep(1)
            if not full_open:
                return True
            continue

        # Bước 5: xử lý hộp thoại Kim Bài Miễn Chiến.
        immunity = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN),
            account=account, log=log,
        )
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
            continue

        # Bước 6: Cẩm Nang chỉ là dấu hiệu nhận diện, không cần thao tác.
        cam_nang = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG),
            account=account, log=log,
        )
        if cam_nang is not None:
            log(f"[{account.username}] Đã nhận diện Cẩm Nang; tiếp tục tìm nút Xuất chiến.")

        # Bước 7: nhận diện Chiến Thuật để chọn đúng bộ tọa độ, rồi click Xuất chiến.
        xuat_chien = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN),
            account=account, log=log,
        )
        if xuat_chien is not None:
            if not full_open:
                log(
                    f"[{account.username}] Đã tới giao diện Xuất chiến; "
                    "dừng tại đây vì chưa chọn tác vụ mở trận."
                )
                return True
            chien_thuat = _match(
                screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT),
                account=account, log=log,
            )
            group = (
                "quan_su.giao_tranh.danh_sach1"
                if chien_thuat is not None
                else "quan_su.giao_tranh.danh_sach2"
            )
            self._battle_hero_position_group = group
            log(
                f"[{account.username}] Chọn bộ tọa độ võ tướng {group} "
                f"({'có' if chien_thuat is not None else 'không có'} Chiến Thuật)."
            )
            x, y = _click_match(device, xuat_chien)
            log(f"[{account.username}] Click Xuất chiến tại ({x}, {y}); chờ vào trận.")
            time.sleep(1)
            return True

        log(
            f"[{account.username}] Mở Giao Tranh — chưa nhận diện được trạng thái "
            f"(lần {attempt}/{max_attempts}); sẽ thử lại."
        )
        time.sleep(1)

    log(f"[{account.username}] Mở Giao Tranh thất bại: quá {max_attempts} lần kiểm tra.")
    return False

