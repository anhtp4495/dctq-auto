"""Thực hiện nhận thưởng trong giao diện Tam Quốc Lệnh."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_TAM_QUOC_LENH_HOP_THOAI_SU_DUNG_KNB_DONG,
    _TEMPLATE_TAM_QUOC_LENH_MIEN_PHI,
    _TEMPLATE_TAM_QUOC_LENH_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH2,
    _TEMPLATE_TAM_QUOC_LENH_THUONG_NHIEM_VU,
    _TEMPLATE_TAM_QUOC_LENH_QUE_BOI_DIEM_BINH_MIEN_PHI,
    _TEMPLATE_TAM_QUOC_LENH_QUE_BOI,
    _TEMPLATE_TAM_QUOC_LENH_DIEM_BINH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_POLL_INTERVAL = 2.5
_TEMPLATES = (
    _TEMPLATE_TAM_QUOC_LENH_MIEN_PHI,
    _TEMPLATE_TAM_QUOC_LENH_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH2,
    _TEMPLATE_TAM_QUOC_LENH_THUONG_NHIEM_VU,
    _TEMPLATE_TAM_QUOC_LENH_HOP_THOAI_SU_DUNG_KNB_DONG,
    _TEMPLATE_TAM_QUOC_LENH_QUE_BOI_DIEM_BINH_MIEN_PHI,
    _TEMPLATE_TAM_QUOC_LENH_QUE_BOI,
    _TEMPLATE_TAM_QUOC_LENH_DIEM_BINH,
)


def run(worker, account, device, log) -> bool:
    """Nhấn lần lượt các mục nhận thưởng đến khi nhận diện trạng thái hoàn tất."""

    log(f"[{account.display_name}] Bắt đầu nhận thưởng Tam Quốc Lệnh.")
    templates = get_templates(_TEMPLATES)

    while True:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang nhận thưởng Tam Quốc Lệnh.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình nhận thưởng: {exc}")
            return False

        action_found = False
        for template_name in _TEMPLATES:
            template = templates.get(template_name)
            if template is None:
                log(
                    f"[{account.display_name}] Không tải được template "
                    f"{template_name}; bỏ qua."
                )
                continue

            found = match(screen, template, account=account, log=log)
            if found is None:
                continue

            if template_name in (
                _TEMPLATE_TAM_QUOC_LENH_QUE_BOI,
                _TEMPLATE_TAM_QUOC_LENH_DIEM_BINH,
            ):
                log(
                    f"[{account.display_name}] Hoàn tất nhận thưởng Tam Quốc Lệnh."
                )
                return True

            try:
                x, y = click_match(device, found)
                action = (
                    "đóng hộp thoại sử dụng KNB"
                    if template_name == _TEMPLATE_TAM_QUOC_LENH_HOP_THOAI_SU_DUNG_KNB_DONG
                    else f"nhận thưởng [{template_name}]"
                )
                log(f"[{account.display_name}] Click {action} tại ({x}, {y}).")
            except Exception as exc:
                log(
                    f"[{account.display_name}] Không click được "
                    f"[{template_name}]: {exc}"
                )
                return False

            action_found = True
            break

        if not action_found:
            log(
                f"[{account.display_name}] Không tìm thấy nút nhận thưởng "
                "hoặc trạng thái hoàn tất Tam Quốc Lệnh."
            )
            return False

        time.sleep(_POLL_INTERVAL)
