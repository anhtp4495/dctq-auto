"""Đóng quy trình Giao Tranh và trở về màn hình chính."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
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


_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)

_MAX_TRIES = 60


def run(
    self,
    account,
    device,
    ocr_client,
    log,
    current_try=1,
) -> bool:
    """Nhận diện trạng thái hiện tại, đóng giao diện và xác nhận đã thoát."""
    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu đóng màn hình Giao Tranh.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.display_name}] Đóng Giao Tranh thất bại: "
            f"quá {_MAX_TRIES} lần kiểm tra."
        )
        return False

    if not self._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang đóng Giao Tranh.")
        return False

    templates = get_templates(_CLOSE_TEMPLATES)

    try:
        screen = _screen_bgr(device)
    except Exception as exc:
        log(
            f"[{account.display_name}] Không chụp được màn hình "
            f"để đóng Giao Tranh: {exc}"
        )
        return False

    positions = ButtonPositions()

    for template_name in _CLOSE_TEMPLATES:
        template = templates.get(template_name)
        if template is None:
            log(
                f"[{account.display_name}] Không tải được template "
                f"{template_name}; bỏ qua."
            )
            continue

        match = _match(screen, template, account=account, log=log)
        if match is None:
            continue

        # Hồi thành: click vào giữa nút rồi kiểm tra lại trạng thái.
        if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH:
            x, y = _click_match(device, match)
            log(f"[{account.display_name}] Click Hồi thành tại ({x}, {y}).")
            time.sleep(1)
            return run(
                self, account, device, ocr_client, log,
                current_try=current_try + 1,
            )

        # Hai màn hình này xác nhận đã thoát khỏi Giao Tranh.
        if template_name in (
            _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
            _TEMPLATE_MAIN_QUAN_SU,
        ):
            log(
                f"[{account.display_name}] Đã thoát khỏi Giao Tranh; "
                "xác nhận trở về màn hình chính."
            )
            return True

        # Đang ở màn hình Tìm đối thủ: hủy tìm kiếm rồi kiểm tra lại.
        if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU:
            x, y = positions.get("quan_su.giao_tranh", "huy_tim_doi_thu")
            device.shell(f"input tap {x} {y}")
            log(
                f"[{account.display_name}] Đang ở màn hình Tìm đối thủ; "
                f"click Hủy tìm đối thủ tại ({x}, {y})."
            )
            time.sleep(1)
            return run(
                self, account, device, ocr_client, log,
                current_try=current_try + 1,
            )

        # Đang ở màn hình Xuất chiến: hủy thao tác xuất chiến rồi kiểm tra lại.
        if template_name == _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN:
            x, y = positions.get("quan_su.giao_tranh", "huy_xuat_chien")
            device.shell(f"input tap {x} {y}")
            log(
                f"[{account.display_name}] Đang ở màn hình Xuất chiến; "
                f"click Hủy xuất chiến tại ({x}, {y})."
            )
            time.sleep(1)
            return run(
                self, account, device, ocr_client, log,
                current_try=current_try + 1,
            )

    log(
        f"[{account.display_name}] Đóng Giao Tranh — chưa nhận diện được trạng thái "
        f"(lần {current_try}/{_MAX_TRIES}); sẽ thử lại."
    )
    time.sleep(1)
    return run(
        self, account, device, ocr_client, log,
        current_try=current_try + 1,
    )
