"""Lớp cơ sở định nghĩa chu kỳ polling và nhận diện trạng thái trận."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOP_THOAI_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
    _TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI,
    _TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN,
    _TEMPLATE_QUAN_SU_TRANH_BA_HOP_THOAI_THU_QUAN,
    _TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU,
    _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH,
    _TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC,
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

    championship_templates = (
        _TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI,
        _TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN,
        _TEMPLATE_QUAN_SU_TRANH_BA_HOP_THOAI_THU_QUAN,
        _TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU,
        _TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH,
        _TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC,
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

        is_championship = context.get("battle_type") == "championship"
        template_names = self.championship_templates if is_championship else self.templates
        templates = get_templates(template_names)
        if is_championship:
            observation = {
                "screen": screen,
                "templates": templates,
                "ration": None,
                "retreat": None,
                "collect": None,
                "withdraw_confirmation": None,
                "next_battle": None,
                "should_end": False,
            }
        else:
            observation = {
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

        # Chỉ nạp và phát event Tranh Bá trong luồng Tranh Bá; không làm
        # thay đổi payload hoặc hành vi polling của Giao Tranh.
        if is_championship:
            observation.update({
                "championship_retreat": match(
                    screen, templates.get(_TEMPLATE_QUAN_SU_TRANH_BA_RUT_LUI),
                    account=account, log=context["log"],
                ),
                "championship_collect": match(
                    screen, templates.get(_TEMPLATE_QUAN_SU_TRANH_BA_THU_QUAN),
                    account=account, log=context["log"],
                ),
                "championship_withdraw_confirmation": match(
                    screen, templates.get(_TEMPLATE_QUAN_SU_TRANH_BA_HOP_THOAI_THU_QUAN),
                    account=account, log=context["log"],
                ),
                "championship_next_battle": match(
                    screen, templates.get(_TEMPLATE_QUAN_SU_TRANH_BA_TRAN_SAU),
                    account=account, log=context["log"],
                ),
                "championship_return_city": match(
                    screen, templates.get(_TEMPLATE_QUAN_SU_TRANH_BA_HOI_THANH),
                    account=account, log=context["log"],
                ),
                "championship_buy_stamina": match(
                    screen, templates.get(_TEMPLATE_QUAN_SU_TRANH_BA_MUA_THE_LUC),
                    account=account, log=context["log"],
                ),
            })
        return observation
