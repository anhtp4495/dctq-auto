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


def _mode(config) -> str:
    if config.get("giao_tranh_nhanh_1_co"):
        return "fast"
    if config.get("ba_co"):
        return "normal"
    if config.get("task_battle_time_mode"):
        return "time_limit"
    return "normal"


def _create_poller(mode):
    if mode == "fast":
        return FastPoller()
    if mode == "time_limit":
        return TimeLimitPoller()
    return NormalPoller()


def run(self, account, device, ocr_client, log) -> bool:
    """Chọn chiến thuật/poller và điều phối các sự kiện trong trận."""
    config = self._config
    mode = _mode(config)
    strategy = PincerBattle()
    poller = _create_poller(mode)
    positions = ButtonPositions()

    context = {
        "worker": self,
        "account": account,
        "device": device,
        "config": config,
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

    target_battles = max(1, int(config.get("task_open_battle_count", 1)))
    completed_battles = 0
    hero_deployed = False
    retreat_requested = False
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
        next_battle = observation["next_battle"]

        if awaiting_next_screen:
            if next_battle is not None:
                continue
            awaiting_next_screen = False

        if next_battle is not None:
            completed_battles += 1
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
            awaiting_next_screen = True
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
            if not config.get("task_end_battle") and mode == "normal":
                log(f"[{account.username}] Đã triển khai đủ võ tướng; hoàn tất Bắt đầu trận.")
                return True
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
            if not config.get("task_end_battle"):
                log(
                    f"[{account.username}] Đã click Thu quân theo chế độ {mode}; "
                    "hoàn tất tác vụ Bắt đầu trận."
                )
                return True
            continue

    log(
        f"[{account.username}] Theo dõi Giao Tranh thất bại: "
        "quá thời gian chờ mà không hoàn thành đủ số trận."
    )
    return False
