"""Điều phối quy trình Giao Tranh bằng Template Matching và tọa độ cấu hình."""

from __future__ import annotations

from dctq_auto.config.constants import (
    _STEP_QUAN_SU_GIAO_TRANH,
)
from dctq_auto.tasks.common.battle import (
    task_close_battle,
    task_open_battle,
    run_battle,
)


_TASK_LABELS = {
    "task_open_battle": "Mở màn hình Giao Tranh",
    "task_use_bazhen": "Sử dụng Canh Bát Trận",
    "task_find_battle_opponent": "Tìm đối thủ Giao Tranh",
    "xuat_chien": "Xuất chiến",
    "task_start_battle": "Bắt đầu trận Giao Tranh",
    "task_end_battle": "Kết thúc trận Giao Tranh",
}



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


def post_battle(log) -> None:
    """Điểm hậu xử lý; hiện tại chỉ ghi log."""
    log("Giao Tranh: hoàn tất quy trình, chưa có xử lý hậu trận.")


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Chạy quy trình Giao Tranh theo các tùy chọn được chọn trong GUI."""
    config = worker._config
    selected = [key for key in _TASK_LABELS if config.get(key)]
    if not selected:
        if _STEP_QUAN_SU_GIAO_TRANH in steps:
            steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
        return steps

    if not pre_battle(config, steps, log):
        for key in selected:
            worker.task_progress_changed.emit(_TASK_LABELS[key], "failed", 0, 1)
        return selected

    failed = []
    for key in selected:
        worker.task_progress_changed.emit(_TASK_LABELS[key], "running", 0, 1)

    needs_open = any(
        config.get(key)
        for key in (
            "task_open_battle", "task_use_bazhen",
            "task_find_battle_opponent", "xuat_chien",
        )
    )
    opened = True
    if needs_open:
        try:
            opened = task_open_battle.run(
                worker, account, device, ocr_client, log, screenshot=screenshot
            )
        except Exception as exc:
            log(f"[{account.username}] Mở Giao Tranh phát sinh lỗi: {exc}")
            opened = False
        if not opened:
            failed.extend(selected)
            for key in selected:
                worker.task_progress_changed.emit(_TASK_LABELS[key], "failed", 0, 1)
        else:
            for key in (
                "task_open_battle", "task_use_bazhen",
                "task_find_battle_opponent", "xuat_chien",
            ):
                if key in selected:
                    worker.task_progress_changed.emit(_TASK_LABELS[key], "done", 1, 1)

    needs_battle = opened and (
        config.get("task_start_battle") or config.get("task_end_battle")
    )
    battle_ok = True
    if needs_battle:
        try:
            battle_ok = run_battle.run(worker, account, device, ocr_client, log)
        except Exception as exc:
            log(f"[{account.username}] Chạy Giao Tranh phát sinh lỗi: {exc}")
            battle_ok = False
        for key in ("task_start_battle", "task_battle_time_mode"):
            if key in selected:
                worker.task_progress_changed.emit(
                    _TASK_LABELS[key],
                    "done" if battle_ok else "failed",
                    1 if battle_ok else 0,
                    1,
                )
                if not battle_ok:
                    failed.append(key)

    if "task_end_battle" in selected and needs_battle and not battle_ok:
        worker.task_progress_changed.emit(
            _TASK_LABELS["task_end_battle"], "failed", 0, 1
        )
        failed.append("task_end_battle")

    if opened and battle_ok and config.get("task_end_battle"):
        try:
            close_ok = task_close_battle.run(worker, account, device, ocr_client, log)
        except Exception as exc:
            log(f"[{account.username}] Hồi thành phát sinh lỗi: {exc}")
            close_ok = False
        if close_ok:
            worker.task_progress_changed.emit(
                _TASK_LABELS["task_end_battle"], "done", 1, 1
            )
        else:
            worker.task_progress_changed.emit(
                _TASK_LABELS["task_end_battle"], "failed", 0, 1
            )
            failed.append("task_end_battle")
    for key in selected:
        if key not in (
            "task_open_battle", "task_use_bazhen",
            "task_find_battle_opponent", "xuat_chien",
            "task_start_battle", "task_battle_time_mode", "task_end_battle",
        ):
            continue
        # Các trạng thái đã được phát ở trên; không phát lại.
    if not failed:
        post_battle(log)
    if _STEP_QUAN_SU_GIAO_TRANH in steps:
        steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
    return failed
