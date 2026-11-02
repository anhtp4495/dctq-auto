"""Điều phối chiến thuật và poller trong quy trình Giao Tranh."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
)
from dctq_auto.tasks.common.battle.battle_strategies.pincer_battle import PincerBattle
from dctq_auto.tasks.common.battle.polling.fast_poller import FastPoller
from dctq_auto.tasks.common.battle.polling.normal_poller import NormalPoller
from dctq_auto.tasks.common.battle.polling.time_limit_poller import TimeLimitPoller
from dctq_auto.tasks.task_battle import get_battle_config


def _create_poller(mode):
    if mode == "fast":
        return FastPoller()
    if mode == "time_limit":
        return TimeLimitPoller()
    return NormalPoller()


def run(self, account, device, ocr_client, log) -> bool:
    """Chọn chiến thuật/poller và điều phối các sự kiện trong trận."""
    config = self._config
    battle = get_battle_config(config)
    mode = battle.mode
    strategy = PincerBattle()
    poller = _create_poller(mode)
    positions = ButtonPositions()

    context = {
        "worker": self,
        "account": account,
        "device": device,
        "config": config,
        "battle_config": battle,
        "log": log,
        "wait_if_paused": self._wait_if_paused,
        # Bộ tọa độ được task_open_battle xác định trước khi click Xuất chiến.
        # Nếu run_battle được gọi độc lập, mặc định dùng danh_sach1.
        "hero_position_group": (
            getattr(self, "_battle_hero_position_group", None)
            or "quan_su.giao_tranh.danh_sach1"
        ),
        "battle_started_at": None,
    }

    target_battles = battle.battle_count
    completed_battles = 0
    # Giữ bộ đếm trên worker để post_battle có thể hậu kiểm sau finally/close.
    self._battle_completed_count = 0
    hero_deployed = False
    retreat_requested = False
    withdraw_confirmation_requested = False
    awaiting_next_screen = False
    deadline = time.monotonic() + max(180, target_battles * 180)

    log(
        f"[{account.username}] Bắt đầu theo dõi Giao Tranh: "
        f"{target_battles} trận, chế độ {mode}."
    )

    while time.monotonic() < deadline:
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang chạy Giao Tranh.")
            return False

        observation = poller.poll(context)
        if observation is None:
            return False

        ration = observation["ration"]
        if ration is not None:
            x, y = positions.get(
                "quan_su.giao_tranh", "xac_nhan_dung_luong_thao"
            )
            device.shell(f"input tap {x} {y}")
            log(
                f"[{account.username}] Phát hiện hộp thoại Dùng lương thảo "
                f"(thiếu tài nguyên khi xuất quân); xác nhận tại ({x}, {y})."
            )
            time.sleep(1)
            continue

        retreat = observation["retreat"]
        collect = observation["collect"]
        withdraw_confirmation = observation["withdraw_confirmation"]
        next_battle = observation["next_battle"]

        if awaiting_next_screen:
            if next_battle is not None:
                continue
            awaiting_next_screen = False

        if next_battle is not None:
            completed_battles += 1
            self._battle_completed_count = completed_battles
            log(
                f"[{account.username}] Phát hiện Trận sau: "
                f"hoàn thành {completed_battles}/{target_battles} trận."
            )
            if completed_battles >= target_battles:
                log(f"[{account.username}] Đã đủ số trận; chuyển sang tác vụ Hồi thành.")
                return True

            from dctq_auto.tasks.common.battle.battle_utils import click_match

            x, y = click_match(device, next_battle)
            log(
                f"[{account.username}] Còn trận tiếp theo; click Trận sau "
                f"tại ({x}, {y}) để chuyển trận."
            )
            hero_deployed = False
            context["battle_started_at"] = None
            retreat_requested = False
            withdraw_confirmation_requested = False
            awaiting_next_screen = True
            continue

        # Nếu Thu quân kết thúc trận ngay, ưu tiên xử lý Trận sau ở trên.
        # Chỉ click xác nhận khi hộp thoại thực sự xuất hiện.
        if withdraw_confirmation is not None and not withdraw_confirmation_requested:
            x, y = positions.get("quan_su.giao_tranh.thu_quan", "xac_nhan")
            device.shell(f"input tap {x} {y}")
            withdraw_confirmation_requested = True
            log(
                f"[{account.username}] Phát hiện hộp thoại Thu quân; "
                f"click Xác nhận tại ({x}, {y})."
            )
            time.sleep(1)
            continue

        if retreat is not None and not hero_deployed:
            log(
                f"[{account.username}] Phát hiện Rút lui; "
                "bắt đầu triển khai đội hình theo chiến thuật gọng kìm."
            )
            context["mark_battle_started"] = (
                lambda: context.__setitem__("battle_started_at", time.monotonic())
            )
            if not strategy.deploy(context):
                return False
            hero_deployed = True
            continue

        if collect is not None and observation["should_end"] and not retreat_requested:
            from dctq_auto.tasks.common.battle.battle_utils import click_match

            x, y = click_match(device, collect)
            retreat_requested = True
            log(
                f"[{account.username}] Điều kiện chế độ {mode} đã đạt; "
                f"click Thu quân tại ({x}, {y})."
            )
            time.sleep(1)
            continue

    log(
        f"[{account.username}] Theo dõi Giao Tranh thất bại: "
        "quá thời gian chờ mà không hoàn thành đủ số trận."
    )
    return False
