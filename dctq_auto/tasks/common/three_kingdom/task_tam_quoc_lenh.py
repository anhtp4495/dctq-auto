"""Nhận thưởng nhanh trong giao diện Tam Quốc Lệnh."""

import time

from dctq_auto.config.constants import (
    _STEP_NHAN_THUONG_TAM_QUOC_LENH,
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
    _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH,
    _TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
)
from dctq_auto.tasks.common.battle.battle_utils import (
    click_match,
    match,
    screen_bgr,
)
from dctq_auto.vision.template_store import get_templates


_MAX_OPEN_TRIES = 20
_MAX_REWARD_TRIES = 10

_OPEN_TEMPLATE_NAMES = (
    _TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH,
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
)
_REWARD_TEMPLATE_NAMES = (
    _TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG,
    _TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH,
)


def pre_tam_quoc_lenh(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn nhận thưởng Tam Quốc Lệnh hay không."""
    if _STEP_NHAN_THUONG_TAM_QUOC_LENH not in steps:
        log("Tam Quốc Lệnh: không có step nhận thưởng trong danh sách; bỏ qua.")
        return False
    return True


def post_tam_quoc_lenh(steps) -> list[str]:
    """Chỉ loại step sau khi quy trình nhận thưởng hoàn tất."""
    if _STEP_NHAN_THUONG_TAM_QUOC_LENH in steps:
        steps.remove(_STEP_NHAN_THUONG_TAM_QUOC_LENH)
    return steps


def open_tam_quoc_lenh(worker, account, device, log) -> bool:
    """Mở Tam Quốc Lệnh từ màn hình chính và xác nhận màn hình đích."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình Tam Quốc Lệnh.")
    templates = get_templates(_OPEN_TEMPLATE_NAMES)

    for attempt in range(1, _MAX_OPEN_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang mở Tam Quốc Lệnh.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình Tam Quốc Lệnh: {exc}")
            return False

        page_match = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_MAN_HINH_CHINH),
            account=account,
            log=log,
        )
        if page_match is not None:
            log(f"[{account.display_name}] Đã xác nhận màn hình Tam Quốc Lệnh.")
            return True

        entry_match = match(
            screen,
            templates.get(_TEMPLATE_MAIN_TAM_QUOC_LENH),
            account=account,
            log=log,
        )
        if entry_match is not None:
            try:
                x, y = click_match(device, entry_match)
                log(
                    f"[{account.display_name}] Click lối vào Tam Quốc Lệnh "
                    f"tại ({x}, {y}); chờ màn hình đích."
                )
            except Exception as exc:
                log(f"[{account.display_name}] Không mở được Tam Quốc Lệnh: {exc}")
                return False
        else:
            log(
                f"[{account.display_name}] Chưa nhận diện được lối vào hoặc "
                f"màn hình Tam Quốc Lệnh (lần {attempt}/{_MAX_OPEN_TRIES})."
            )

        time.sleep(1)

    log(f"[{account.display_name}] Mở Tam Quốc Lệnh thất bại sau {_MAX_OPEN_TRIES} lần thử.")
    return False


def receive_tam_quoc_lenh_reward(worker, account, device, log) -> bool:
    """Mở tab nhận thưởng, nhấn nhận nhanh và chờ xác nhận đã nhận."""
    templates = get_templates(_REWARD_TEMPLATE_NAMES)

    for attempt in range(1, _MAX_REWARD_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Nhận thưởng Tam Quốc Lệnh đã dừng theo yêu cầu.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình nhận thưởng: {exc}")
            return False

        unopened_tab_match = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_CHUA_NHAN_THUONG),
            account=account,
            log=log,
        )
        if unopened_tab_match is not None:
            try:
                x, y = click_match(device, unopened_tab_match)
                log(
                    f"[{account.display_name}] Mở tab nhận thưởng Tam Quốc Lệnh "
                    f"tại ({x}, {y})."
                )
            except Exception as exc:
                log(f"[{account.display_name}] Không mở được tab nhận thưởng: {exc}")
                return False
            time.sleep(0.7)
            continue

        quick_reward_match = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_NHAN_THUONG_NHANH),
            account=account,
            log=log,
        )
        if quick_reward_match is not None:
            try:
                x, y = click_match(device, quick_reward_match)
                log(
                    f"[{account.display_name}] Click nhận thưởng nhanh "
                    f"tại ({x}, {y}); chờ xác nhận."
                )
            except Exception as exc:
                log(f"[{account.display_name}] Không click được nhận thưởng nhanh: {exc}")
                return False
            time.sleep(0.8)
            continue

        selected_tab_match = match(
            screen,
            templates.get(_TEMPLATE_TAM_QUOC_LENH_DA_NHAN_THUONG),
            account=account,
            log=log,
        )
        if selected_tab_match is not None:
            log(
                f"[{account.display_name}] Tab nhận thưởng đã mở và "
                "không còn nút nhận thưởng nhanh; xác nhận hoàn tất."
            )
            return True

        log(
            f"[{account.display_name}] Chưa nhận diện được trạng thái nhận thưởng "
            f"(lần {attempt}/{_MAX_REWARD_TRIES})."
        )
        time.sleep(0.8)

    log(
        f"[{account.display_name}] Không xác nhận được đã nhận thưởng Tam Quốc Lệnh "
        f"sau {_MAX_REWARD_TRIES} lần kiểm tra."
    )
    return False


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Mở Tam Quốc Lệnh và nhận thưởng; giữ nguyên step nếu chưa xác nhận thành công."""
    if not pre_tam_quoc_lenh(steps, log):
        return steps

    if not open_tam_quoc_lenh(worker, account, device, log):
        return steps

    if not receive_tam_quoc_lenh_reward(worker, account, device, log):
        return steps

    return post_tam_quoc_lenh(steps)
