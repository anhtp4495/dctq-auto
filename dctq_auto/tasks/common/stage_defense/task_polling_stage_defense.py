"""Polling templates used by the Mưu Binh stage-defense flow."""

from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MUU_BINH,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
    _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO,
    _TEMPLATE_MUU_BINH_BAT_DAU,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.vision.template_store import get_templates


TEMPLATE_NAMES = (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_CHIEN_TRANH_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_MUU_BINH,
    _TEMPLATE_MUU_BINH_BAT_DAU,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
)


def poll(device, account, log):
    """Capture one frame and return matches keyed by each template's short name."""
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
        name.rsplit("/", 1)[-1]: match(screen, templates.get(name), account=account, log=log)
        for name in TEMPLATE_NAMES
    }
