"""Mở màn hình và điều hướng vào quy trình Giao Tranh."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.tasks.common.battle.battle_utils import click_match as _click_match


_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)

_MAX_TRIES = 60


def detect_group(screen_bgr, account, log) -> str:
    """Nhận diện Chiến Thuật để chọn bộ tọa độ võ tướng."""
    template_name = _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT
    templates = get_templates((template_name,))
    template = templates.get(template_name)

    if template is None:
        log(
            f"[{account.username}] Không tải được template {template_name}; "
            "mặc định dùng danh sách võ tướng 2."
        )
        return "quan_su.giao_tranh.danh_sach2"

    try:
        match = match_template(
            screen_bgr,
            template.image,
            threshold=template.threshold,
            method=template.method,
            search_rect=template.search_rect,
            grayscale=template.grayscale,
        )
    except (ValueError, cv2.error) as exc:
        log(
            f"[{account.username}] Lỗi template matching {template_name}: {exc}; "
            "mặc định dùng danh sách võ tướng 2."
        )
        return "quan_su.giao_tranh.danh_sach2"

    if match is None:
        return "quan_su.giao_tranh.danh_sach2"

    report_template_match(
        log,
        context=f"[{account.username}]",
        template=template,
        match=match,
    )
    return "quan_su.giao_tranh.danh_sach1"


def _handle_template_match(
    self,
    template_name,
    template,
    match,
    screen_bgr,
    account,
    device,
    ocr_client,
    log,
    current_try,
    positions,
) -> bool | None:
    """Xử lý hành động tương ứng với template vừa nhận diện.

    Trả về None nếu cần tiếp tục kiểm tra template khác.
    """
    report_template_match(
        log,
        context=f"[{account.username}]",
        template=template,
        match=match,
    )

    # Lối vào Giao Tranh.
    if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO:
        x, y = _click_match(device, match)
        log(f"[{account.username}] Click lối vào Giao Tranh tại ({x}, {y}).")
        time.sleep(1)
        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Khu vực Quân Sự.
    if template_name == _TEMPLATE_MAIN_QUAN_SU:
        x, y = _click_match(device, match)
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
    if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN:
        if not self._config.get("task_use_bazhen"):
            return None

        x, y = _click_match(device, match)
        log(f"[{account.username}] Click sử dụng Canh Bát Trận tại ({x}, {y}).")
        time.sleep(1)

        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Tìm đối thủ.
    if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU:
        x, y = _click_match(device, match)
        log(f"[{account.username}] Click Tìm đối thủ tại ({x}, {y}).")
        time.sleep(1)

        return run(
            self, account, device, ocr_client, log,
            current_try=current_try + 1,
        )

    # Bài Miễn Chiến.
    if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN:
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

    # Xuất chiến: chỉ lúc này mới nhận diện Chiến Thuật để chọn group.
    if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN:
        hero_position_group = detect_group(screen_bgr, account, log)
        self._battle_hero_position_group = hero_position_group
        log(
            f"[{account.username}] Chọn bộ tọa độ võ tướng "
            f"{hero_position_group}."
        )

        x, y = _click_match(device, match)
        log(
            f"[{account.username}] Click Xuất chiến tại ({x}, {y}); "
            "chờ vào trận."
        )
        time.sleep(1)
        return True

    return None


def run(
    self,
    account,
    device,
    ocr_client,
    log,
    screenshot=None,
    current_try=1,
) -> bool:
    """Điều hướng vào Giao Tranh bằng cách nhận diện và xử lý từng template."""
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

    template_names = _OPEN_TEMPLATES
    templates = get_templates(template_names)

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(
            f"[{account.username}] Không chụp được màn hình "
            f"để nhận diện Giao Tranh: {exc}"
        )
        return False

    positions = ButtonPositions()

    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            log(
                f"[{account.username}] Không tải được template "
                f"{template_name}; bỏ qua."
            )
            continue

        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=template.search_rect,
                grayscale=template.grayscale,
            )
        except (ValueError, cv2.error) as exc:
            log(
                f"[{account.username}] Lỗi template matching "
                f"{template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        result = _handle_template_match(
            self=self,
            template_name=template_name,
            template=template,
            match=match,
            screen_bgr=screen_bgr,
            account=account,
            device=device,
            ocr_client=ocr_client,
            log=log,
            current_try=current_try,
            positions=positions,
        )
        if result is not None:
            return result

    log(
        f"[{account.username}] Mở Giao Tranh — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); sẽ thử lại."
    )
    time.sleep(1)
    return run(
        self, account, device, ocr_client, log,
        current_try=current_try + 1,
    )
