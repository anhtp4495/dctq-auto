"""Run the simple Mưu Binh auto-deploy/reward loop."""

import time

from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.stage_defense.task_polling_stage_defense import poll


_MAX_SECONDS = 100 * 240


def run(worker, account, device, log) -> bool:
    """Repeat Xuất chiến and reward selection until timeout or main screen."""
    deadline = time.monotonic() + _MAX_SECONDS
    log(f"[{account.username}] Bắt đầu tự động vượt ải Mưu Binh (tối đa {_MAX_SECONDS // 60} phút).")

    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang vượt ải Mưu Binh.")
            return False

        observation = poll(device, account, log)
        if observation is None:
            return False

        # Clear exit condition: stage 100 completed and the game returned home.
        if observation["quan_su"] is not None:
            log(f"[{account.username}] Đã hoàn thành Mưu Binh; phát hiện màn hình chính Quân Sự.")
            return True

        # The reward dialog is only actionable when one of its reward choices is visible.
        if observation["hop_thoai_thuong_vuot_ai"] is not None:
            reward = next((
                (name, observation[name])
                for name in ("thuong_vuot_ai_1", "thuong_vuot_ai_2", "thuong_vuot_ai_3")
                if observation[name] is not None
            ), None)
            if reward is not None:
                reward_name, match = reward
                x, y = click_match(device, match)
                log(f"[{account.username}] Chọn {reward_name} tại ({x}, {y}).")
                time.sleep(1)
                continue
            time.sleep(0.5)
            continue

        if observation["tu_dong_den_ai_tiep_theo"] is not None:
            x, y = click_match(device, observation["tu_dong_den_ai_tiep_theo"])
            log(f"[{account.username}] Click Tự động đến ải tiếp theo tại ({x}, {y}).")
            time.sleep(1)
            continue

        if observation["xuat_chien"] is not None:
            x, y = click_match(device, observation["xuat_chien"])
            log(f"[{account.username}] Click Xuất chiến tại ({x}, {y}).")
            time.sleep(1)
            continue

        time.sleep(1)

    log(f"[{account.username}] Dừng Mưu Binh vì đã hết thời gian {_MAX_SECONDS // 60} phút.")
    return True
