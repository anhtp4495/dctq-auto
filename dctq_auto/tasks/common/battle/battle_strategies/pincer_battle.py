"""Chiến thuật gọng kìm: A -> B thả 2 tướng, B -> A thả 3 tướng."""

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT
import time
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import (
    match,
    screen_bgr,
    swipe,
)

from .base_battle import BaseBattle


class PincerBattle(BaseBattle):
    """Triển khai 5 võ tướng theo hai cửa bằng thao tác kéo gọng kìm."""

    def prepare(self, context) -> bool:
        account = context["account"]
        try:
            screen = screen_bgr(context["device"])
        except Exception as exc:
            context["log"](
                f"[{account.username}] Không chụp được màn hình để chọn bộ võ tướng: {exc}"
            )
            return False

        templates = get_templates((_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,))
        strategy_match = match(
            screen,
            templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT),
            account=account,
            log=context["log"],
        )
        group = (
            "quan_su.giao_tranh.danh_sach1"
            if strategy_match is not None
            else "quan_su.giao_tranh.danh_sach2"
        )
        context["hero_position_group"] = group
        context["log"](
            f"[{account.username}] Chọn bộ tọa độ võ tướng {group} "
            f"({'có' if strategy_match is not None else 'không có'} Chiến Thuật)."
        )
        return True

    def deploy(self, context) -> bool:
        account = context["account"]
        device = context["device"]
        log = context["log"]
        if not context.get("hero_position_group") and not self.prepare(context):
            return False

        positions = ButtonPositions()
        group = context["hero_position_group"]
        hero_points = [
            positions.get(group, f"vo_tuong_{index}")
            for index in range(1, 6)
        ]
        battle_points = [
            positions.get(
                "quan_su.giao_tranh", f"vi_tri_chien_dau_vo_tuong_{index}"
            )
            for index in range(1, 6)
        ]
        point_a = positions.get(
            "quan_su.giao_tranh", "diem_bat_dau_giao_tranh_1"
        )
        point_b = positions.get(
            "quan_su.giao_tranh", "diem_bat_dau_giao_tranh_2"
        )

        # Mở cửa thứ nhất và triển khai hai võ tướng đầu tiên.
        for repeat in range(1, 3):
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng khi kéo điểm A -> B ({repeat}/2).")
                return False
            swipe(device, point_a, point_b)
            time.sleep(0.3)
            log(
                f"[{account.username}] Kéo điểm A -> B lần {repeat}/2: "
                f"{point_a} -> {point_b}."
            )

        for index in range(2):
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng trước khi thả võ tướng {index + 1}.")
                return False
            if index == 0 and context.get("mark_battle_started"):
                context["mark_battle_started"]()
            swipe(device, hero_points[index], battle_points[index])
            time.sleep(0.3)
            log(
                f"[{account.username}] Thả võ tướng {index + 1}/5: "
                f"{hero_points[index]} -> {battle_points[index]}."
            )

        # Mở cửa thứ hai và triển khai ba võ tướng còn lại.
        for repeat in range(1, 3):
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng khi kéo điểm B -> A ({repeat}/2).")
                return False
            swipe(device, point_b, point_a)
            time.sleep(0.3)
            log(
                f"[{account.username}] Kéo điểm B -> A lần {repeat}/2: "
                f"{point_b} -> {point_a}."
            )

        for index in range(2, 5):
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng trước khi thả võ tướng {index + 1}.")
                return False
            swipe(device, hero_points[index], battle_points[index])
            log(
                f"[{account.username}] Thả võ tướng {index + 1}/5: "
                f"{hero_points[index]} -> {battle_points[index]}."
            )

        log(f"[{account.username}] Đã triển khai đủ 5 võ tướng theo chiến thuật gọng kìm.")
        return True
