"""Close the Mưu Binh screen and verify return to its entry point."""

import time

from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.stage_defense.task_polling_stage_defense import poll


def run(worker, account, device, log, max_tries: int = 15) -> bool:
    for attempt in range(1, max_tries + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang đóng Mưu Binh.")
            return False
        observation = poll(device, account, log)
        if observation is None:
            return False

        if observation["loi_vao"] is not None:
            log(f"[{account.display_name}] Đã trở về màn hình Lối vào Mưu Binh.")
            return True

        if observation["hoi_thanh"] is not None:
            x, y = click_match(device, observation["hoi_thanh"])
            log(f"[{account.display_name}] Click Hồi thành khi đóng Mưu Binh tại ({x}, {y}).")
            time.sleep(1.5)
            continue

        log(
            f"[{account.display_name}] Đóng Mưu Binh — chưa xác nhận được màn hình thoát "
            f"(lần {attempt}/{max_tries})."
        )
        time.sleep(1)

    log(f"[{account.display_name}] Chưa xác nhận được đã thoát Mưu Binh.")
    return False
