"""Run the simple Mưu Binh auto-deploy/reward loop."""

import random
import time
from pathlib import Path

from PIL import Image

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
    _TEMPLATE_MUU_BINH_RUT_LUI,
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

# Chỉnh vùng cắt ảnh tại đây: (left, top, right, bottom).
_STAGE_SCREENSHOT_RECT = (670, 20, 1250, 80)
_STAGE_IMAGE_WIDTH = _STAGE_SCREENSHOT_RECT[2] - _STAGE_SCREENSHOT_RECT[0]
_STAGE_IMAGE_HEIGHT = _STAGE_SCREENSHOT_RECT[3] - _STAGE_SCREENSHOT_RECT[1]
_STAGE_IMAGE_COUNT = 100
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


def _save_stage_screenshot(device, account, log, stage_number: int) -> None:
    """Save the configured top status strip after a stage reward is confirmed."""
    try:
        image = device.screenshot()
        left, top, right, bottom = _STAGE_SCREENSHOT_RECT
        if image.width < right or image.height < bottom:
            raise ValueError(
                f"Kích thước màn hình không đủ để cắt vùng "
                f"{_STAGE_IMAGE_WIDTH}x{_STAGE_IMAGE_HEIGHT}: {image.width}x{image.height}"
            )

        if not 1 <= stage_number <= 100:
            raise ValueError(f"Số ải phải nằm trong khoảng 1-100, nhận được: {stage_number}")

        # Mỗi ải chiếm một hàng cố định trong canvas 100 ải.
        row = image.crop(_STAGE_SCREENSHOT_RECT).convert("RGBA")
        pixels = []
        for red, green, blue, _alpha in row.getdata():
            darkest = min(red, green, blue)
            brightest = max(red, green, blue)
            if darkest >= 180 and brightest - darkest <= 60:
                alpha = min(255, max(0, int((darkest - 160) * 255 / 95)))
                pixels.append((255, 255, 255, alpha))
            else:
                pixels.append((0, 0, 0, 0))
        row.putdata(pixels)

        output_dir = Path("artifacts/screenshots")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "danh_sach_ai.png"
        combined = Image.new(
            "RGBA",
            (_STAGE_IMAGE_WIDTH, _STAGE_IMAGE_COUNT * _STAGE_IMAGE_HEIGHT),
            (0, 0, 0, 0),
        )
        if output_path.exists():
            with Image.open(output_path) as existing_file:
                existing = existing_file.convert("RGBA")
            if existing.size == combined.size:
                combined.paste(existing, (0, 0))
            elif existing.width == _STAGE_IMAGE_WIDTH:
                # Giữ dữ liệu cũ dạng nối dọc nếu cùng chiều rộng.
                copy_height = min(existing.height, combined.height)
                combined.paste(
                    existing.crop((0, 0, _STAGE_IMAGE_WIDTH, copy_height)),
                    (0, 0),
                )
            existing.close()

        combined.paste(row, (0, (stage_number - 1) * _STAGE_IMAGE_HEIGHT))
        combined.save(output_path, format="PNG")
        log(
            f"[{account.display_name}] Đã thêm ảnh ải {stage_number} "
            f"vào danh sách: {output_path}"
        )
    except Exception as exc:
        log(f"[{account.display_name}] Không lưu được ảnh ải {stage_number}: {exc}")


def run(worker, account, device, log) -> bool:
    """Repeat Xuất chiến and reward selection until timeout or main screen."""
    deadline = time.monotonic() + _MAX_SECONDS
    log(f"[{account.display_name}] Bắt đầu tự động vượt ải Mưu Binh (tối đa {_MAX_SECONDS // 60} phút).")

    templates = get_templates(
        _REWARD_TEMPLATES
        + (_TEMPLATE_MUU_BINH_RUT_LUI, _TEMPLATE_MUU_BINH_XAC_NHAN_THUONG_VUOT_AI)
    )
    positions = ButtonPositions()

    config = getattr(worker, "_config", {}) or {}
    save_screenshot = bool(config.get("muu_binh_save_screenshot", False))
    try:
        stage_number = min(100, max(1, int(config.get("muu_binh_stage_number", 1))))
    except (TypeError, ValueError):
        stage_number = 1

    completed_stages = 0
    battle_screenshot_saved = False
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
            battle_screenshot_saved = False
            worker._emit_task_progress("Nhận thưởng", "running", 0, 0)
            reward_confirmed = _handle_reward_dialog(
                device, account, log, templates, positions
            )
            if reward_confirmed:
                stage_number += 1
                worker._config["muu_binh_stage_number"] = stage_number
                worker.stage_number_changed.emit(stage_number)
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

        if observation["rut_lui"] is not None:
            if not battle_screenshot_saved:
                if save_screenshot and stage_number <= 100:
                    _save_stage_screenshot(device, account, log, stage_number)
                battle_screenshot_saved = True
                log(f"[{account.display_name}] Đã ghi nhận trạng thái đang chiến đấu ở ải {stage_number}.")
            worker._emit_task_progress("Chiến đấu", "running", 0, 0)
            worker._emit_task_progress("Nhận thưởng", "pending", 0, 0)
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
