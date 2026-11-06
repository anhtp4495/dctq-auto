"""Điều phối chiến thuật và poller trong quy trình Giao Tranh."""

import time
from pathlib import Path

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _STEP_QUAN_SU_GIAO_TRANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
)
from dctq_auto.tasks.common.battle.battle_strategies.custom_battle import CustomBattle
from dctq_auto.tasks.common.battle.polling.fast_poller import FastPoller
from dctq_auto.tasks.common.battle.polling.normal_poller import NormalPoller
from dctq_auto.tasks.common.battle.polling.time_limit_poller import TimeLimitPoller
from dctq_auto.tasks.common.battle.battle_config import get_battle_config


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
    strategy = CustomBattle()
    poller = _create_poller(mode)
    positions = ButtonPositions()

    # task_open_battle nhận diện danh sách võ tướng trước khi vào trận.
    # Mỗi danh sách có một JSON mặc định; cấu hình có thể chỉ định file khác.
    hero_position_group = (
        getattr(self, "_battle_hero_position_group", None)
        or "quan_su.giao_tranh.danh_sach1"
    )
    default_strategy_name = (
        "pincer_battle_danh_sach2.json"
        if hero_position_group.endswith("danh_sach2")
        else "pincer_battle_danh_sach1.json"
    )
    strategy_path = config.get("battle_strategy_path") or (
        Path(__file__).resolve().parent
        / "battle_strategies"
        / "ranked"
        / default_strategy_name
    )

    context = {
        "worker": self,
        "account": account,
        "device": device,
        "config": config,
        "battle_config": battle,
        "log": log,
        "battle_strategy_path": strategy_path,
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
        f"[{account.display_name}] Bắt đầu theo dõi Giao Tranh: "
        f"{target_battles} trận, chế độ {mode}."
    )

    while time.monotonic() < deadline:
        if not self._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang chạy Giao Tranh.")
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
                f"[{account.display_name}] Phát hiện hộp thoại Dùng lương thảo "
                f"(thiếu tài nguyên khi xuất quân); xác nhận tại ({x}, {y})."
            )
            time.sleep(1)
            continue

        retreat = observation["retreat"]
        collect = observation["collect"]
        withdraw_confirmation = observation["withdraw_confirmation"]
        next_battle = observation["next_battle"]

        if awaiting_next_screen and next_battle is None:
            # Template đã biến mất; sẵn sàng ghi nhận trận kế tiếp.
            awaiting_next_screen = False

        if next_battle is not None:
            if not awaiting_next_screen:
                completed_battles += 1
                self._battle_completed_count = completed_battles
                log(
                    f"[{account.display_name}] Phát hiện Trận sau: "
                    f"hoàn thành {completed_battles}/{target_battles} trận."
                )
                if completed_battles >= target_battles:
                    log(f"[{account.display_name}] Đã đủ số trận; chuyển sang tác vụ Hồi thành.")
                    return True

            from dctq_auto.tasks.common.battle.battle_utils import click_match

            # Cứ mỗi lần polling còn thấy Trận sau thì click lại, không tăng
            # bộ đếm trận cho đến khi template biến mất rồi xuất hiện lại.
            x, y = click_match(device, next_battle)
            log(
                f"[{account.display_name}] Còn trận tiếp theo; click Trận sau "
                f"tại ({x}, {y}) để chuyển trận."
            )
            hero_deployed = False
            context["battle_started_at"] = None
            context["time_limit_reached_logged"] = False
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
                f"[{account.display_name}] Phát hiện hộp thoại Thu quân; "
                f"click Xác nhận tại ({x}, {y})."
            )
            time.sleep(1)
            continue

        if retreat is not None and not hero_deployed:
            log(
                f"[{account.display_name}] Phát hiện Rút lui; "
                "bắt đầu triển khai đội hình theo chiến thuật JSON."
            )
            self.UpdateProcessInfo(
                process_id=self._current_process_ids[_STEP_QUAN_SU_GIAO_TRANH],
                current=completed_battles + 1,
                total=target_battles,
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
                f"[{account.display_name}] Điều kiện chế độ {mode} đã đạt; "
                f"click Thu quân tại ({x}, {y})."
            )
            time.sleep(1)
            continue

    log(
        f"[{account.display_name}] Theo dõi Giao Tranh thất bại: "
        "quá thời gian chờ mà không hoàn thành đủ số trận."
    )
    return False
