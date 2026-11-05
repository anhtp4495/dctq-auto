""""Đóng các dialog đã biết đang mở trên màn hình game."""

import cv2

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
    _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
    _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


def close_knowned_dialog(
    self, account, device, ocr_client, log, screen_bgr
) -> bool:
    """Đóng dialog đã biết trên ảnh BGR được cung cấp; không tự chụp màn hình."""
    template_names = (
        _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
        _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
        _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH,
    )
    templates = get_templates(template_names)
    positions = ButtonPositions()

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
                f"[{account.username}] Lỗi matching template "
                f"{template.id}: {exc}"
            )
            continue

        if match is None:
            continue

        report_template_match(
            log,
            context=f"[{account.username}]",
            template=template,
            match=match,
        )

        if template_name == _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN:
            x, y = click_match(device, match)
            dialog_name = "Đóng cập nhật thông tin"
        elif template_name == _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN:
            x, y = positions.get("main.cap_nhat_thong_tin", "dong_man_hinh")
            device.shell(f"input tap {x} {y}")
            dialog_name = "Cập nhật thông tin"
        else:
            x, y = positions.get("main.dich_quan_tap_kich", "dong_man_hinh")
            device.shell(f"input tap {x} {y}")
            dialog_name = "Địch Quân Tập Kích"

        log(
            f"[{account.username}] Đã phát hiện {dialog_name}; "
            f"click đóng màn hình tại ({x}, {y})."
        )
        return True

    return False
"