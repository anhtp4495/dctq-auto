"""Polling templates used by the Mưu Binh stage-defense flow."""

from dctq_auto.config.constants import (
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
    _TEMPLATE_MUU_BINH_LOI_VAO,
    _TEMPLATE_MUU_BINH_RUT_LUI,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
    _TEMPLATE_MUU_BINH_XUAT_CHIEN,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.vision.template_store import get_templates


TEMPLATE_NAMES = (
    _TEMPLATE_MUU_BINH_LOI_VAO,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_XUAT_CHIEN,
    _TEMPLATE_MUU_BINH_RUT_LUI,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
)


def poll(device, account, log):
    """Capture one frame and return every currently matched Mưu Binh template."""
    templates = get_templates(TEMPLATE_NAMES)
    if not templates:
        log(
            f"[{account.username}] Không tải được template Mưu Binh. "
            "Kiểm tra ảnh nguồn và rect/search_rect trong templates.json."
        )
        return None

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình Mưu Binh: {exc}")
        return None

    return {
        name: match(screen, templates.get(name), account=account, log=log)
        for name in TEMPLATE_NAMES
    }
