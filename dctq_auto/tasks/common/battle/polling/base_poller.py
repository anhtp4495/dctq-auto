"""Lớp cơ sở định nghĩa chu kỳ polling và nhận diện trạng thái trận."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOP_THOAI_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr


class BasePoller:
    """Poller cơ sở; lớp con chỉ bổ sung điều kiện riêng của chế độ."""

    templates = (
        _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_HOP_THOAI_THU_QUAN,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
    )

    def poll(self, context) -> dict | None:
        """Giữ nhịp polling 3 giây rồi thực hiện nhận diện của lớp con."""
        time.sleep(3)
        return self.check(context)

    def check(self, context) -> dict | None:
        """Đọc các trạng thái chung xuất hiện trong màn hình giao tranh."""
        account = context["account"]
        try:
            screen = screen_bgr(context["device"])
        except Exception as exc:
            context["log"](f"[{account.username}] Không chụp được màn hình trận đấu: {exc}")
            return None

        templates = get_templates(self.templates)
        return {
            "screen": screen,
            "templates": templates,
            "ration": match(
                screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO),
                account=account, log=context["log"],
            ),
            "retreat": match(
                screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI),
                account=account, log=context["log"],
            ),
            "collect": match(
                screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN),
                account=account, log=context["log"],
            ),
            "withdraw_confirmation": match(
                screen,
                templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_HOP_THOAI_THU_QUAN),
                account=account, log=context["log"],
            ),
            "next_battle": match(
                screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU),
                account=account, log=context["log"],
            ),
            "should_end": False,
        }
