"""Open the Mưu Binh stage-defense screen from the War menu."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.battle.battle_utils import click_match, swipe
from dctq_auto.tasks.common.stage_defense.task_polling_stage_defense import poll


_MAX_TRIES = 60


def run(worker, account, device, log) -> bool:
    """Navigate into Mưu Binh; the run loop handles Xuất chiến and rewards."""
    log(f"[{account.username}] Bắt đầu mở Mưu Binh.")
    positions = ButtonPositions()
    has_swiped_war_menu = False

    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang mở Mưu Binh.")
            return False

        observation = poll(device, account, log)
        if observation is None:
            return False

        # Đã vào màn hình Quân Sự: kết thúc bước mở.
        if observation["quan_su"] is not None:
            log(f"[{account.username}] Đã trở về màn hình chính Quân Sự khi mở Mưu Binh.")
            return False

        # Màn hình chính Chiến Tranh có hai trang; chỉ được swipe một lần.
        if observation["man_hinh_chinh"] is not None:
            if has_swiped_war_menu:
                try:
                    close_point = positions.get("chien_tranh", "dong_man_hinh")
                    x, y = close_point
                    device.shell(f"input tap {x} {y}")
                    log(
                        f"[{account.username}] Đã swipe nhưng vẫn ở màn hình Chiến Tranh; "
                        f"đóng màn hình tại ({x}, {y}). Vào Mưu Binh Thất bại."
                    )
                except (KeyError, ValueError) as exc:
                    log(
                        f"[{account.username}] Không tìm thấy tọa độ đóng màn hình Chiến Tranh: {exc}. "
                        "Vào Mưu Binh Thất bại."
                    )
                return False

            start = positions.get("chien_tranh", "item_2")
            end = positions.get("chien_tranh", "item_1")
            swipe(device, start, end, account=account, log=log)
            has_swiped_war_menu = True
            time.sleep(1)
            continue

        if observation["muu_binh"] is not None:
            x, y = click_match(device, observation["muu_binh"])
            log(f"[{account.username}] Click Mưu Binh tại ({x}, {y}).")
            time.sleep(1)
            continue

        if observation["chien_dau"] is not None:
            x, y = click_match(device, observation["chien_dau"])
            log(f"[{account.username}] Click Chiến đấu tại ({x}, {y}).")
            time.sleep(1)
            continue

        if observation["tu_dong_den_ai_tiep_theo"] is not None:
            x, y = click_match(device, observation["tu_dong_den_ai_tiep_theo"])
            log(f"[{account.username}] Click Tự động đến ải tiếp theo tại ({x}, {y}).")
            time.sleep(1)
            continue

        if any(observation[name] is not None for name in (
            "xuat_chien", "hoi_thanh", "hop_thoai_thuong_vuot_ai"
        )):
            log(f"[{account.username}] Đã mở Mưu Binh thành công; chuyển sang tự động vượt ải.")
            return True

        log(
            f"[{account.username}] Mở Mưu Binh — chưa nhận diện được trạng thái "
            f"(lần {attempt}/{_MAX_TRIES}); thử lại."
        )
        time.sleep(1)

    log(f"[{account.username}] Vào Mưu Binh Thất bại sau {_MAX_TRIES} lần kiểm tra.")
    return False
