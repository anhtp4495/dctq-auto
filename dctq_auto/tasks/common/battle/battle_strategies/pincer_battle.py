"""Chiến thuật gọng kìm: A -> B thả 2 tướng, B -> A thả 3 tướng."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.battle.battle_utils import swipe, tap

from .base_battle import BaseBattle


class PincerBattle(BaseBattle):
    """Triển khai 5 võ tướng theo hai cửa bằng thao tác kéo gọng kìm."""

    def deploy(self, context) -> bool:
        account = context["account"]
        device = context["device"]
        log = context["log"]
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

        def deploy_hero(index: int) -> bool:
            hero_number = index + 1
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng trước khi chọn võ tướng {hero_number}.")
                return False
            if index == 0 and context.get("mark_battle_started"):
                context["mark_battle_started"]()

            tap(device, hero_points[index], account=account, log=log)
            time.sleep(0.3)
            log(
                f"[{account.username}] Chọn võ tướng {hero_number}/5 tại "
                f"{hero_points[index]}."
            )

            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng trước khi thả võ tướng {hero_number}.")
                return False
            tap(device, battle_points[index], account=account, log=log)
            time.sleep(0.3)
            log(
                f"[{account.username}] Thả võ tướng {hero_number}/5 tại "
                f"{battle_points[index]}."
            )
            return True

        # Mở cửa thứ nhất và triển khai hai võ tướng đầu tiên.
        for repeat in range(1, 3):
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng khi kéo điểm A -> B ({repeat}/2).")
                return False
            swipe(device, point_a, point_b, account=account, log=log)
            time.sleep(0.3)
            log(
                f"[{account.username}] Kéo điểm A -> B lần {repeat}/2: "
                f"{point_a} -> {point_b}."
            )

        for index in range(2):
            if not deploy_hero(index):
                return False

        # Mở cửa thứ hai và triển khai ba võ tướng còn lại.
        for repeat in range(1, 3):
            if not context["wait_if_paused"]():
                log(f"[{account.username}] Đã dừng khi kéo điểm B -> A ({repeat}/2).")
                return False
            swipe(device, point_b, point_a, account=account, log=log)
            time.sleep(0.3)
            log(
                f"[{account.username}] Kéo điểm B -> A lần {repeat}/2: "
                f"{point_b} -> {point_a}."
            )

        for index in range(2, 5):
            if not deploy_hero(index):
                return False

        log(f"[{account.username}] Đã triển khai đủ 5 võ tướng theo chiến thuật gọng kìm.")
        return True
