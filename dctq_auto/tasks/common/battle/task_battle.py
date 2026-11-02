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

    battle = get_battle_config(config)
    return {
        **config,
        # Clone Optimize luôn chạy trọn quy trình từ màn hình chính đến Hồi thành.
        "task_open_battle": True,
        "task_use_bazhen": False,
        "task_find_battle_opponent": True,
        "xuat_chien": True,
        "task_start_battle": True,
        "task_end_battle": True,
        "task_open_battle_count": battle.battle_count,
        "giao_tranh_nhanh_1_co": battle.mode == "fast",
        "ba_co": battle.mode == "normal",
        "task_battle_time_mode": battle.mode == "time_limit",
        "task_battle_time_limit": battle.time_limit_seconds,
    }


def _mode(config) -> str:
    if config.get("giao_tranh_nhanh_1_co"):
        return "fast"
    if config.get("ba_co"):
        return "normal"
    if config.get("task_battle_time_mode"):
        return "time_limit"
    return "normal"


def pre_battle(config, steps, log) -> bool:
    """Kiểm tra cấu hình Giao Tranh trước khi bắt đầu."""
    if _STEP_QUAN_SU_GIAO_TRANH not in steps:
        log("Giao Tranh: thiếu step quan_su_giao_tranh trong danh sách steps.")
        return False

    try:
        battle_count = int(config.get("task_open_battle_count", 1))
        if battle_count < 1:
            raise ValueError("Số trận phải lớn hơn hoặc bằng 1.")

        selected_modes = sum(
            bool(config.get(key))
            for key in ("giao_tranh_nhanh_1_co", "ba_co", "task_battle_time_mode")
        )
        if selected_modes > 1:
            raise ValueError("Chỉ được chọn một chế độ chiến đấu Giao Tranh.")

        if config.get("task_battle_time_mode"):
            seconds = int(
                config.get("task_battle_time_limit")
                or config.get("thoi_gian_giao_tranh")
                or 0
            )
            if seconds < 1:
                raise ValueError("Thời gian tối đa Giao Tranh phải lớn hơn 0 giây.")
    except (TypeError, ValueError) as exc:
        log(f"Giao Tranh: cấu hình không hợp lệ: {exc}")
        return False

    log(
        f"Giao Tranh: cấu hình hợp lệ — {battle_count} trận, "
        f"chế độ {_mode(config)}."
    )
    return True


def post_battle(worker, account, device, log) -> bool:
    """Xác nhận đã thoát giao diện trận và hoàn thành đủ số trận yêu cầu."""
    target_battles = max(1, int(worker._config.get("task_open_battle_count", 1)))
    completed_battles = int(getattr(worker, "_battle_completed_count", 0))

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.username}] Hậu kiểm Giao Tranh: không chụp được màn hình: {exc}")
        return False

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
        log(f"[{account.username}] Hậu kiểm thành công: đã đóng Giao Tranh và đủ số trận.")
        return True

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
    return False


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Chạy tuần tự pre_battle → open → battle → finally close → post_battle."""
    config = worker._config
    selected = [key for key in ("task_start_battle", "task_end_battle") if config.get(key)]
    if not selected:
        if _STEP_QUAN_SU_GIAO_TRANH in steps:
            steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
        return steps

    # Không thực hiện bất kỳ thao tác UI nào nếu cấu hình không hợp lệ.
    if not pre_battle(config, steps, log):
        for key in selected:
            label = "Bắt đầu trận Giao Tranh" if key == "task_start_battle" else "Kết thúc trận Giao Tranh"
            worker.task_progress_changed.emit(label, "failed", 0, 1)
        return selected

    for key in selected:
        worker.task_progress_changed.emit(_TASK_LABELS[key], "running", 0, 1)

    failed = []
    opened = False
    battle_ok = False
    post_ok = False

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
        post_ok = post_battle(worker, account, device, log)
    except Exception as exc:
        log(f"[{account.username}] Hậu kiểm Giao Tranh phát sinh lỗi: {exc}")
        post_ok = False

    if "task_start_battle" in selected:
        worker.task_progress_changed.emit(
            "Bắt đầu trận Giao Tranh",
            "done" if battle_ok else "failed",
            1 if battle_ok else 0,
            1,
        )
        if not battle_ok:
            failed.append("task_start_battle")

    if "task_end_battle" in selected:
        worker.task_progress_changed.emit(
            "Kết thúc trận Giao Tranh",
            "done" if post_ok else "failed",
            1 if post_ok else 0,
            1,
        )
        if not post_ok:
            failed.append("task_end_battle")

    if _STEP_QUAN_SU_GIAO_TRANH in steps:
        steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
    return list(dict.fromkeys(failed))
