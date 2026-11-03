"""Run the simple Mưu Binh auto-deploy/reward loop."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_GIET_NHANH,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_6,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_4,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_2,
    _TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI,
)
from dctq_auto.tasks.common.battle.battle_utils import (
    click_match,
    match,
    screen_bgr,
    tap,
)
from dctq_auto.tasks.common.stage_defense.task_polling_stage_defense import poll
from dctq_auto.vision.template_store import get_templates


_MAX_SECONDS = 100 * 240
_REWARD_TEMPLATES = (
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_GIET_NHANH,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_6,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_4,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_2,
)


def _handle_reward_dialog(device, account, log, templates, positions) -> bool:
    """Chọn một thưởng nhận diện được và xử lý nút xác nhận."""
    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình chọn thưởng Mưu Binh: {exc}")
        return False

    selected = None
    for template_name in _REWARD_TEMPLATES:
        template = templates.get(template_name)
        found = match(screen, template, account=account, log=log)
        if found is not None:
            selected = (template_name, found)
            break

    if selected is None:
        log(f"[{account.username}] Hộp thoại thưởng vượt ải đang mở nhưng chưa nhận diện được lựa chọn thưởng.")
        return False

    reward_name, reward_match = selected
    x, y = click_match(device, reward_match)
    log(f"[{account.username}] Chọn thưởng {reward_name.rsplit('/', 1)[-1]} tại ({x}, {y}).")
    time.sleep(0.5)

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình kiểm tra xác nhận thưởng: {exc}")
        screen = None

    confirm_template = templates.get(_TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI)
    confirm_match = (
        match(screen, confirm_template, account=account, log=log)
        if screen is not None
        else None
    )
    if confirm_match is not None:
        x, y = click_match(device, confirm_match)
        log(f"[{account.username}] Click Xác nhận thưởng vượt ải theo template tại ({x}, {y}).")
    else:
        try:
            point = positions.get("chien_tranh.muu_binh", "xac_nhan_thuong_vuot_ai")
            tap(device, point, account=account, log=log)
            log(
                f"[{account.username}] Không match template xác nhận thưởng; "
                f"click tọa độ dự phòng tại ({point[0]}, {point[1]})."
            )
        except (KeyError, ValueError) as exc:
            log(f"[{account.username}] Không lấy được tọa độ xác nhận thưởng Mưu Binh: {exc}")
            return False

    return True


def run(worker, account, device, log) -> bool:
    """Repeat Xuất chiến and reward selection until timeout or main screen."""
    deadline = time.monotonic() + _MAX_SECONDS
    log(f"[{account.username}] Bắt đầu tự động vượt ải Mưu Binh (tối đa {_MAX_SECONDS // 60} phút).")

    templates = get_templates(
        _REWARD_TEMPLATES + (_TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI,)
    )
    positions = ButtonPositions()

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

        # Chỉ xử lý hộp thoại thưởng khi đã nhận diện được hộp thoại.
        if observation["hop_thoai_thuong_vuot_ai"] is not None:
            if _handle_reward_dialog(device, account, log, templates, positions):
                time.sleep(1)
            else:
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
