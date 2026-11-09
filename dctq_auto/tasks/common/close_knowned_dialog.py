"""Đóng các dialog đã biết đang mở trên màn hình game."""

import cv2
import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_HOAT_DONG,
    _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
    _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
    _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH,
    _TEMPLATE_MAIN_SU_KIEN_TANG_QUA_HANG_NGAY,
    _TEMPLATE_MAIN_SU_KIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_MAIN_SU_KIEN_THOAT,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH,
)
from dctq_auto.tasks.common.battle.battle_utils import (
    click_match as _click_match,
    match as _match,
    screen_bgr as _screen_bgr,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates

_MAX_TRIES = 3

def close_knowned_dialog(
    self, account, device, ocr_client, log, screen_bgr
) -> bool:
    """Đóng dialog đã biết trên ảnh BGR được cung cấp; không tự chụp màn hình."""
    template_names = (
        _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
        _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
        _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH,
        _TEMPLATE_MAIN_SU_KIEN_TANG_QUA_HANG_NGAY,
        _TEMPLATE_MAIN_SU_KIEN_AN_CHO_TRONG_DE_THOAT,
        _TEMPLATE_MAIN_SU_KIEN_THOAT,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
        _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH,
        _TEMPLATE_MAIN_HOAT_DONG,
    )
    templates = get_templates(template_names)
    positions = ButtonPositions()

    for attempt in range(1, _MAX_TRIES + 1):
        if not self._wait_if_paused():
            return False

        for template_name in template_names:
            template = templates.get(template_name)
            if template is None:
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
                    f"[{account.display_name}] Lỗi matching template "
                    f"{template.id}: {exc}"
                )
                continue

            if match is None:
                continue

            report_template_match(
                log,
                context=f"[{account.display_name}]",
                template=template,
                match=match,
            )

            if template_name ==_TEMPLATE_MAIN_HOAT_DONG:
                log(
                    f"[{account.display_name}] Không có hộp thoại nào cả!"
                )
                return True

            if template_name == _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN:
                x, y = _click_match(device, match)
                dialog_name = "Đóng cập nhật thông tin"
            elif template_name == _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN:
                x, y = positions.get("main.cap_nhat_thong_tin", "dong_man_hinh")
                device.shell(f"input tap {x} {y}")
                dialog_name = "Cập nhật thông tin"
            elif template_name == _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH:
                x, y = positions.get("main.dich_quan_tap_kich", "dong_man_hinh")
                device.shell(f"input tap {x} {y}")
                dialog_name = "Địch Quân Tập Kích"
            elif template_name in ( _TEMPLATE_MAIN_SU_KIEN_TANG_QUA_HANG_NGAY, _TEMPLATE_MAIN_SU_KIEN_AN_CHO_TRONG_DE_THOAT, _TEMPLATE_MAIN_SU_KIEN_THOAT,):
                x, y = _click_match(device, match)
                dialog_name = "Tặng quà sự kiện1"
                log(
                    f"[{account.display_name}] Đã phát hiện {dialog_name}; "
                    f"click đóng màn hình tại ({x}, {y})."
                )
                time.sleep(4)
                return close_knowned_dialog(self, account, device, ocr_client, log, screen_bgr=_screen_bgr(device))
            else:
                x, y = _click_match(device, match)
                dialog_name = template_name
                time.sleep(1.5)

            log(
                f"[{account.display_name}] Đã phát hiện {dialog_name}; "
                f"click đóng màn hình tại ({x}, {y})."
            )
            break

    return False
