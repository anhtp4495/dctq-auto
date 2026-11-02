"""Điều phối quy trình Giao Tranh bằng Template Matching và tọa độ cấu hình."""

from __future__ import annotations

from dctq_auto.config.constants import (
    _STEP_QUAN_SU_GIAO_TRANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import match, screen_bgr
from dctq_auto.tasks.common.battle import (
    task_close_battle,
    task_open_battle,
    run_battle,
)


def build_clone_battle_config(config) -> dict:
    """Chuyển BattleConfig của Clone Optimize sang cấu hình task Giao Tranh."""
    from dctq_auto.tasks.task_battle import get_battle_config

    return {
        **config,
        "battle_config": get_battle_config(config),
    }


def pre_battle(config, steps, log) -> bool:
    """Kiểm tra cấu hình Giao Tranh trước khi bắt đầu."""
    if _STEP_QUAN_SU_GIAO_TRANH not in steps:
        log("Giao Tranh: thiếu step quan_su_giao_tranh trong danh sách steps.")
        return False

    from dctq_auto.tasks.task_battle import get_battle_config

    try:
        battle = get_battle_config(config)
    except (TypeError, ValueError) as exc:
        log(f"Giao Tranh: cấu hình không hợp lệ: {exc}")
        return False

    log(
        f"Giao Tranh: cấu hình hợp lệ — {battle.battle_count} trận, "
        f"chế độ {battle.mode}, giới hạn {battle.time_limit_seconds} giây."
    )
    return True


def post_battle(worker, account, steps, device, log) -> list[str]:
    """Ghi log hậu kiểm, loại step Giao Tranh và trả lại steps còn lại."""
    from dctq_auto.tasks.task_battle import get_battle_config

    target_battles = get_battle_config(worker._config).battle_count
    completed_battles = int(getattr(worker, "_battle_completed_count", 0))

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.username}] Hậu kiểm Giao Tranh: không chụp được màn hình: {exc}")
        if _STEP_QUAN_SU_GIAO_TRANH in steps:
            steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
        return steps

    templates = get_templates((
        _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    ))
    closed_template = None
    for template_name in (
        _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
        _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    ):
        found = match(
            screen,
            templates.get(template_name),
            account=account,
            log=log,
        )
        if found is not None:
            closed_template = template_name
            break

    screen_closed = closed_template is not None
    count_reached = completed_battles >= target_battles

    log(
        f"[{account.username}] Hậu kiểm Giao Tranh: "
        f"đã đóng màn hình={screen_closed}, "
        f"số trận={completed_battles}/{target_battles}."
    )
    if screen_closed and count_reached:
        log(f"[{account.username}] Hậu kiểm: đã đóng Giao Tranh và đủ số trận.")

    if not screen_closed:
        log(
            f"[{account.username}] Hậu kiểm thất bại: chưa nhận diện được "
            "Hồi thành hoặc Lối vào Giao Tranh."
        )
    if not count_reached:
        log(
            f"[{account.username}] Hậu kiểm thất bại: số trận hoàn thành "
            f"chưa đạt yêu cầu ({completed_battles}/{target_battles})."
        )
    if _STEP_QUAN_SU_GIAO_TRANH in steps:
        steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Chạy tuần tự pre_battle → open → battle → finally close → post_battle."""
    config = worker._config
    # Không thực hiện bất kỳ thao tác UI nào nếu cấu hình không hợp lệ.
    if not pre_battle(config, steps, log):
        return post_battle(worker, account, steps, device, log)

    opened = False
    battle_ok = False

    try:
        # Bước 1: mở Giao Tranh.
        opened = task_open_battle.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        )
        if not opened:
            log(f"[{account.username}] Không mở được Giao Tranh; bỏ qua run_battle.")
        else:
            # Bước 2: chạy và đếm số trận.
            battle_ok = run_battle.run(worker, account, device, ocr_client, log)

    except Exception as exc:
        log(f"[{account.username}] Quy trình Giao Tranh phát sinh lỗi: {exc}")

    finally:
        # Luôn thử đóng giao diện kể cả open/battle trả False hoặc phát sinh exception.
        try:
            close_ok = task_close_battle.run(worker, account, device, ocr_client, log)
            log(
                f"[{account.username}] Tác vụ đóng Giao Tranh "
                f"{'thành công' if close_ok else 'chưa xác nhận được'}."
            )
        except Exception as exc:
            log(f"[{account.username}] Đóng Giao Tranh phát sinh lỗi: {exc}")

    # Bước 4: hậu kiểm độc lập sau khi finally đã chạy xong.
    try:
        return post_battle(worker, account, steps, device, log)
    except Exception as exc:
        log(f"[{account.username}] Hậu kiểm Giao Tranh phát sinh lỗi: {exc}")
        if _STEP_QUAN_SU_GIAO_TRANH in steps:
            steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
        return steps
