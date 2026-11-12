"""Polling templates used only by the Mưu Binh stage-running loop."""

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_MUU_BINH_RUT_LUI,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
)
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.vision.template_store import get_templates


TEMPLATE_NAMES = (
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_MUU_BINH_CHIEN_DAU,
    _TEMPLATE_MUU_BINH_RUT_LUI,
    _TEMPLATE_MUU_BINH_HOI_THANH,
    _TEMPLATE_MUU_BINH_TU_DONG_DEN_AI_TIEP_THEO,
    _TEMPLATE_MUU_BINH_HOP_THOAI_THUONG_VUOT_AI,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
)


def poll(device, account, log):
    """Capture one frame and return stage-running matches keyed by template short name."""
    templates = get_templates(TEMPLATE_NAMES)
    if not templates:
        log(
            f"[{account.display_name}] Không tải được template Mưu Binh. "
            "Kiểm tra ảnh nguồn và rect/search_rect trong templates.json."
        )
        return None

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình Mưu Binh: {exc}")
        return None

    # Giữ đủ key để task_run_stage_defense có thể truy cập an toàn,
    # nhưng dừng matching ngay khi tìm thấy template đầu tiên.
    observation = {
        name.rsplit("/", 1)[-1]: None
        for name in TEMPLATE_NAMES
    }
    for name in TEMPLATE_NAMES:
        found = match(screen, templates.get(name), account=account, log=log)
        if found is not None:
            observation[name.rsplit("/", 1)[-1]] = found
            return observation

    return observation
