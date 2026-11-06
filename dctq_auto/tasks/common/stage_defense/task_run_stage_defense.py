"""Run the simple Mưu Binh auto-deploy/reward loop."""

import random
import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_GIET_NHANH,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_10,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_6,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_4,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_2,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_TRUONG_THANH_10,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
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
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_10,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_6,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_4,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_CUONG_CONG_2,
    _TEMPLATE_CHIEN_TRANH_THUONG_VUOT_AI_TRUONG_THANH_10,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_1,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_2,
    _TEMPLATE_MUU_BINH_THUONG_VUOT_AI_3,
)
_REWARD_FALLBACK_BUTTONS = (
    "thuong_vuot_ai_1",
    "thuong_vuot_ai_2",
    "thuong_vuot_ai_3",
)


def _handle_reward_dialog(device, account, log, templates, positions) -> bool:
    """Chọn một thưởng nhận diện được và xử lý nút xác nhận."""
    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình chọn thưởng Mưu Binh: {exc}")
        return False

    selected = None
    for template_name in _REWARD_TEMPLATES:
        template = templates.get(template_name)
        found = match(screen, template, account=account, log=log)
        if found is not None:
            selected = (template_name, found)
            break

    if selected is not None:
        reward_name, reward_match = selected
        x, y = click_match(device, reward_match)
        log(f"[{account.display_name}] Chọn thưởng {reward_name.rsplit('/', 1)[-1]} tại ({x}, {y}).")
    else:
        fallback_name = random.choice(_REWARD_FALLBACK_BUTTONS)
        try:
            point = positions.get("chien_tranh.muu_binh", fallback_name)
            tap(device, point, account=account, log=log)
            log(
                f"[{account.display_name}] Không match 7 template thưởng; "
                f"chọn ngẫu nhiên {fallback_name} tại ({point[0]}, {point[1]})."
            )
        except (KeyError, ValueError) as exc:
            log(f"[{account.display_name}] Không lấy được tọa độ thưởng Mưu Binh {fallback_name}: {exc}")
            return False

    # Dùng lại ảnh đã chụp khi quét 7 lựa chọn, không chụp màn hình lần nữa.
    confirm_template = templates.get(_TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI)
    confirm_match = match(screen, confirm_template, account=account, log=log)
    if confirm_match is not None:
        x, y = click_match(device, confirm_match)
        log(f"[{account.display_name}] Click Xác nhận thưởng vượt ải theo template tại ({x}, {y}).")
    else:
        try:
            point = positions.get("chien_tranh.muu_binh", "xac_nhan_thuong_vuot_ai")
            tap(device, point, account=account, log=log)
            log(
                f"[{account.display_name}] Không match template xác nhận thưởng; "
                f"click tọa độ dự phòng tại ({point[0]}, {point[1]})."
            )
        except (KeyError, ValueError) as exc:
            log(f"[{account.display_name}] Không lấy được tọa độ xác nhận thưởng Mưu Binh: {exc}")
            return False

    return True


def run(worker, account, device, log) -> bool:
    """Repeat Xuất chiến and reward selection until timeout or main screen."""
    deadline = time.monotonic() + _MAX_SECONDS
    log(f"[{account.display_name}] Bắt đầu tự động vượt ải Mưu Binh (tối đa {_MAX_SECONDS // 60} phút).")

    templates = get_templates(
        _REWARD_TEMPLATES + (_TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI,)
    )
    positions = ButtonPositions()

    completed_stages = 0
    worker._emit_task_progress("Chiến đấu", "pending", 0, 0)
    worker._emit_task_progress("Nhận thưởng", "pending", 0, 0)
    worker._set_progress_root_message("Đã vượt ải 0")

    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang vượt ải Mưu Binh.")
            return False

        observation = poll(device, account, log)
        if observation is None:
            return False

        if observation["quan_su"] is not None:
            worker._emit_task_progress("Chiến đấu", "success", 0, 0)
            worker._emit_task_progress("Nhận thưởng", "success", 0, 0)
            log(
                f"[{account.display_name}] Đã hoàn thành Mưu Binh; "
                "phát hiện màn hình chính Quân Sự."
            )
            return True

        if observation["hop_thoai_thuong_vuot_ai"] is not None:
            worker._emit_task_progress("Nhận thưởng", "running", 0, 0)
            _handle_reward_dialog(device, account, log, templates, positions)
            completed_stages += 1
            worker._set_progress_root_message(
                f"Đã vượt ải {min(completed_stages, 100)}"
            )
            worker._emit_task_progress("Chiến đấu", "running", 0, 0)
            worker._emit_task_progress("Nhận thưởng", "pending", 0, 0)
            time.sleep(1)
            continue

        if observation["tu_dong_den_ai_tiep_theo"] is not None:
            x, y = click_match(device, observation["tu_dong_den_ai_tiep_theo"])
            log(f"[{account.display_name}] Click Tự động đến ải tiếp theo tại ({x}, {y}).")
            time.sleep(1)
            continue

        if observation["chien_dau"] is not None:
            worker._emit_task_progress("Chiến đấu", "running", 0, 0)
            worker._emit_task_progress("Nhận thưởng", "pending", 0, 0)
            x, y = click_match(device, observation["chien_dau"])
            log(f"[{account.display_name}] Click Chiến đấu tại ({x}, {y}).")
            time.sleep(1)
            continue

        time.sleep(3)

    log(f"[{account.display_name}] Dừng Mưu Binh vì đã hết thời gian {_MAX_SECONDS // 60} phút.")
    return True
