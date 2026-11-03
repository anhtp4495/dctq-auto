"""Điều phối trọn quy trình Tranh Bá."""

from typing import Any, Mapping

from dctq_auto.config.constants import _STEP_QUAN_SU_TRANH_BA
from dctq_auto.tasks.common.battle.battle_config import BattleConfig, get_battle_config
from . import (
    task_close_ranked_battle,
    task_open_ranked_battle,
    task_run_ranked_battle,
)


def build_ranked_battle_config(
    value: Mapping[str, Any] | BattleConfig | None = None,
) -> BattleConfig:
    """Tạo cấu hình Tranh Bá với các giá trị mặc định riêng."""
    if isinstance(value, BattleConfig):
        return value
    value = value or {}
    return BattleConfig(
        battle_count=int(value.get("battle_count", 6)),
        mode=value.get("mode", "time_limit"),
        time_limit_seconds=int(value.get("time_limit_seconds", 45)),
        refill=bool(value.get("refill", False)),
    )


def pre_battle(config, steps, log) -> bool:
    """Kiểm tra lựa chọn và số trận Tranh Bá."""
    if _STEP_QUAN_SU_TRANH_BA not in steps:
        log("Không chọn chức năng [Tranh Bá].")
        return False
    try:
        battle = (
            config.get("battle_config")
            if isinstance(config.get("battle_config"), BattleConfig)
            else build_ranked_battle_config(config.get("ranked_battle_config"))
        )
        count = battle.battle_count
    except (TypeError, ValueError) as exc:
        log(f"Tranh Bá: cấu hình không hợp lệ: {exc}")
        return False
    log(
        f"Tranh Bá: cấu hình hợp lệ — {count} trận, "
        f"chế độ {battle.mode}, giới hạn {battle.time_limit_seconds} giây."
    )
    return True


def post_battle(worker, steps, log) -> list[str]:
    """Hậu kiểm số trận và loại step Tranh Bá khỏi danh sách."""
    if _STEP_QUAN_SU_TRANH_BA not in steps:
        return steps
    try:
        target = get_battle_config(worker._config).battle_count
    except (TypeError, ValueError):
        target = 6
    completed = int(getattr(worker, "_ranked_battle_completed_count", 0))
    if completed < target:
        log(f"Tranh Bá chưa đủ số trận: {completed}/{target}.")
    else:
        log(f"Tranh Bá đã hoàn thành đủ {completed}/{target} trận.")
    steps.remove(_STEP_QUAN_SU_TRANH_BA)
    return steps


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Mở Tranh Bá, chạy các trận, luôn thử đóng giao diện và hậu kiểm."""
    worker._ranked_battle_completed_count = 0
    worker._ranked_battle_success = False
    if not pre_battle(worker._config, steps, log):
        return post_battle(worker, steps, log)

    battle_ok = False
    try:
        opened = task_open_ranked_battle.run(worker, account, device, ocr_client, log)
        if not opened:
            log(f"[{account.username}] Không mở được Tranh Bá; bỏ qua phần theo dõi trận.")
        else:
            battle_ok = task_run_ranked_battle.run(
                worker, account, device, ocr_client, log
            )
    except Exception as exc:
        log(f"[{account.username}] Quy trình Tranh Bá phát sinh lỗi: {exc}")
    finally:
        try:
            closed = task_close_ranked_battle.run(worker, account, device, ocr_client, log)
            log(
                f"[{account.username}] Đóng giao diện Tranh Bá "
                f"{'thành công' if closed else 'chưa xác nhận được'}."
            )
        except Exception as exc:
            log(f"[{account.username}] Đóng Tranh Bá phát sinh lỗi: {exc}")

    target = get_battle_config(worker._config).battle_count
    completed = int(getattr(worker, "_ranked_battle_completed_count", 0))
    worker._ranked_battle_success = bool(battle_ok and completed >= target)
    return post_battle(worker, steps, log)
