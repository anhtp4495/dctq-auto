"""Run and monitor the Mưu Binh stage-defense sequence."""

import time

from dctq_auto.tasks.common.battle.battle_strategies.pincer_battle import PincerBattle
from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.stage_defense.task_polling_stage_defense import poll


_TOTAL_STAGES = 100
_MAX_SECONDS = _TOTAL_STAGES * 240


def detect_current_stage(observation) -> int | None:
    """Stage detection is intentionally disabled until the grid is calibrated."""
    # TODO: map the danh_sach_ai template-match center to its 10x10 grid cell.
    # Keep returning None for now: unknown stage must never advance progress.
    return None


def run(worker, account, device, log) -> bool:
    """Poll Mưu Binh, deploy heroes, and handle stage rewards/return-city."""
    strategy = PincerBattle()
    hero_deployed = False
    completed_stage = 0
    deadline = time.monotonic() + _MAX_SECONDS
    context = {
        "worker": worker,
        "account": account,
        "device": device,
        "config": worker._config,
        "log": log,
        "wait_if_paused": worker._wait_if_paused,
        "hero_position_group": "quan_su.giao_tranh.danh_sach1",
        "battle_started_at": None,
    }

    log(f"[{account.username}] Bắt đầu theo dõi Mưu Binh: tối đa {_TOTAL_STAGES} ải.")
    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang vượt ải Mưu Binh.")
            return False

        observation = poll(device, account, log)
        if observation is None:
            return False

        detected_stage = detect_current_stage(observation)
        if isinstance(detected_stage, int) and 1 <= detected_stage <= _TOTAL_STAGES:
            # A detected stage N confirms every preceding stage as complete.
            if detected_stage > completed_stage:
                for stage in range(completed_stage + 1, detected_stage + 1):
                    worker.task_progress_changed.emit(f"Ải {stage}", "done", 1, 1)
                completed_stage = detected_stage
                worker.progress_changed.emit(
                    completed_stage, _TOTAL_STAGES,
                    f"Đã xác định tiến trình Mưu Binh: Ải {completed_stage}/100",
                )
                log(
                    f"[{account.username}] Xác định được Ải {detected_stage}; "
                    f"đánh dấu Ải 1–{detected_stage} thành công."
                )
        # None/unknown is deliberately a no-op: don't change any progress row.

        if observation["hoi_thanh"] is not None:
            x, y = click_match(device, observation["hoi_thanh"])
            log(f"[{account.username}] Phát hiện Hồi thành; click tại ({x}, {y}).")
            time.sleep(2)
            return True

        if observation["hop_thoai_thuong_vuot_ai"] is not None:
            reward = next((
                observation[name]
                for name in ("thuong_vuot_ai_1", "thuong_vuot_ai_2", "thuong_vuot_ai_3")
                if observation[name] is not None
            ), None)
            if reward is not None:
                x, y = click_match(device, reward)
                log(
                    f"[{account.username}] Chọn thưởng vượt ải tại ({x}, {y}); "
                    "chờ chuyển sang ải tiếp theo."
                )
                time.sleep(1.5)
                hero_deployed = False
                context["battle_started_at"] = None
                continue
            log(f"[{account.username}] Đã thấy hộp thoại thưởng vượt ải; chờ nhận diện lựa chọn.")
            time.sleep(1)
            continue

        if observation["rut_lui"] is not None and not hero_deployed:
            log(
                f"[{account.username}] Phát hiện Rút lui; "
                "triển khai đội hình theo chiến thuật gọng kìm."
            )
            context["mark_battle_started"] = (
                lambda: context.__setitem__("battle_started_at", time.monotonic())
            )
            if not strategy.deploy(context):
                return False
            hero_deployed = True
            continue

        if observation["xuat_chien"] is not None:
            x, y = click_match(device, observation["xuat_chien"])
            log(f"[{account.username}] Click Xuất chiến tại ({x}, {y}).")
            time.sleep(1)
            continue

        if observation["chien_dau"] is not None:
            x, y = click_match(device, observation["chien_dau"])
            log(f"[{account.username}] Click Chiến đấu để tiếp tục vượt ải tại ({x}, {y}).")
            time.sleep(1)
            hero_deployed = False
            context["battle_started_at"] = None
            continue

        time.sleep(1)

    log(
        f"[{account.username}] Vượt Ải Mưu Binh hết thời gian chờ; "
        f"đã xác nhận tiến trình đến Ải {completed_stage}/100."
    )
    return False
