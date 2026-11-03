"""Open the Mưu Binh stage-defense screen."""

import time

from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.stage_defense.task_polling_stage_defense import poll


_MAX_TRIES = 60


def run(worker, account, device, log) -> bool:
    """Navigate into Mưu Binh; the run loop handles Xuất chiến and rewards."""
    log(f"[{account.username}] Bắt đầu mở Mưu Binh.")
    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang mở Mưu Binh.")
            return False

        observation = poll(device, account, log)
        if observation is None:
            return False

        if observation["loi_vao"] is not None:
            x, y = click_match(device, observation["loi_vao"])
            log(f"[{account.username}] Click Lối vào Mưu Binh tại ({x}, {y}).")
            time.sleep(1)
            continue

        if observation["chien_dau"] is not None:
            x, y = click_match(device, observation["chien_dau"])
            log(f"[{account.username}] Click Chiến đấu tại ({x}, {y}).")
            time.sleep(1)
            continue

        if any(observation[name] is not None for name in (
            "xuat_chien", "tu_dong_den_ai_tiep_theo", "hop_thoai_thuong_vuot_ai"
        )):
            log(f"[{account.username}] Đã vào luồng vượt ải Mưu Binh; chuyển sang theo dõi.")
            return True

        log(
            f"[{account.username}] Mở Mưu Binh — chưa nhận diện được trạng thái "
            f"(lần {attempt}/{_MAX_TRIES}); thử lại."
        )
        time.sleep(1)

    log(f"[{account.username}] Mở Mưu Binh thất bại sau {_MAX_TRIES} lần kiểm tra.")
    return False
