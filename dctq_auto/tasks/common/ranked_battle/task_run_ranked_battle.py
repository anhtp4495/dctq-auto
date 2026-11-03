"""Theo dõi và điều phối các trận Tranh Bá."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.battle.battle_strategies.pincer_battle import PincerBattle
from dctq_auto.tasks.common.battle.polling.normal_poller import NormalPoller
from dctq_auto.tasks.common.battle.battle_config import get_battle_config


def run(self, account, device, ocr_client, log) -> bool:
    """Chạy đủ số trận Tranh Bá, dùng polling để nhận diện trạng thái."""
    battle_config = get_battle_config(self._config)
    target = battle_config.battle_count
    time_limit = battle_config.time_limit_seconds
    poller = NormalPoller()
    strategy = PincerBattle()
    positions = ButtonPositions()
    context = {
        "worker": self,
        "account": account,
        "device": device,
        "config": self._config,
        "battle_config": battle_config,
        "log": log,
        "wait_if_paused": self._wait_if_paused,
        "battle_type": "championship",
        "hero_position_group": (
            getattr(self, "_battle_hero_position_group", None)
            or "quan_su.giao_tranh.danh_sach1"
        ),
        "battle_started_at": None,
    }

    completed = 0
    self._ranked_battle_completed_count = 0
    hero_deployed = False
    withdraw_requested = False
    withdraw_confirmation_requested = False
    awaiting_next_screen = False
    deadline = time.monotonic() + max(180, target * (time_limit + 120))

    log(
        f"[{account.username}] Bắt đầu theo dõi Tranh Bá: "
        f"{target} trận, chế độ {battle_config.mode}, "
        f"giới hạn mỗi trận {time_limit} giây."
    )

    while time.monotonic() < deadline:
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang chạy Tranh Bá.")
            return False

        observation = poller.poll(context)
        if observation is None:
            return False

        buy_stamina = observation.get("championship_buy_stamina")
        if buy_stamina is not None:
            button = (
                "xac_nhan_mua_the_luc"
                if battle_config.refill
                else "huy_mua_the_luc"
            )
            x, y = positions.get("quan_su.tranh_ba", button)
            device.shell(f"input tap {x} {y}")
            if battle_config.refill:
                log(
                    f"[{account.username}] Đã chọn mua lượt Tranh Bá bằng KNB "
                    f"tại ({x}, {y}); tiếp tục theo dõi."
                )
                time.sleep(2)
                continue
            log(
                f"[{account.username}] Không bật refill; đã hủy mua lượt "
                f"tại ({x}, {y}), kết thúc chiến đấu."
            )
            return False

        next_battle = observation.get("championship_next_battle")
        return_city = observation.get("championship_return_city")
        retreat = observation.get("championship_retreat")
        collect = observation.get("championship_collect")
        confirmation = observation.get("championship_withdraw_confirmation")

        if awaiting_next_screen and next_battle is None:
            awaiting_next_screen = False

        if next_battle is not None:
            if not awaiting_next_screen:
                completed += 1
                self._ranked_battle_completed_count = completed
                log(f"[{account.username}] Hoàn thành Tranh Bá {completed}/{target} trận.")
                awaiting_next_screen = True
                if completed >= target:
                    if return_city is not None:
                        x, y = click_match(device, return_city)
                        log(f"[{account.username}] Đã đủ số trận; click Hồi thành tại ({x}, {y}).")
                        return True
                    log(f"[{account.username}] Đã đủ số trận; chờ nút Hồi thành xuất hiện.")
                    time.sleep(1)
                    continue

            if completed < target:
                x, y = click_match(device, next_battle)
                log(f"[{account.username}] Còn trận tiếp theo; click Trận sau tại ({x}, {y}).")
                hero_deployed = False
                withdraw_requested = False
                withdraw_confirmation_requested = False
                context["battle_started_at"] = None
                awaiting_next_screen = True
                continue

        if completed >= target and return_city is not None:
            x, y = click_match(device, return_city)
            log(f"[{account.username}] Đã đủ số trận; click Hồi thành tại ({x}, {y}).")
            return True

        if confirmation is not None and not withdraw_confirmation_requested:
            x, y = positions.get("quan_su.giao_tranh.thu_quan", "xac_nhan")
            device.shell(f"input tap {x} {y}")
            withdraw_confirmation_requested = True
            log(f"[{account.username}] Xác nhận Thu quân Tranh Bá tại ({x}, {y}).")
            time.sleep(1)
            continue

        if retreat is not None and not hero_deployed:
            log(f"[{account.username}] Phát hiện Rút lui; triển khai đội hình.")
            context["mark_battle_started"] = (
                lambda: context.__setitem__("battle_started_at", time.monotonic())
            )
            if not strategy.deploy(context):
                return False
            hero_deployed = True
            withdraw_requested = False
            continue

        started_at = context.get("battle_started_at")
        if collect is not None and started_at is not None and not withdraw_requested:
            elapsed = time.monotonic() - started_at
            should_withdraw = (
                battle_config.mode == "fast"
                or (
                    battle_config.mode == "time_limit"
                    and elapsed >= time_limit
                )
            )
            if should_withdraw:
                x, y = click_match(device, collect)
                withdraw_requested = True
                reason = (
                    "chế độ nhanh"
                    if battle_config.mode == "fast"
                    else f"đã đủ {time_limit} giây"
                )
                log(
                    f"[{account.username}] {reason}; "
                    f"click Thu quân tại ({x}, {y})."
                )
                time.sleep(1)
                continue

        if return_city is not None and completed >= target:
            x, y = click_match(device, return_city)
            log(f"[{account.username}] Click Hồi thành tại ({x}, {y}).")
            return True

    log(
        f"[{account.username}] Theo dõi Tranh Bá thất bại: "
        f"hết thời gian chờ ({completed}/{target} trận)."
    )
    return False
