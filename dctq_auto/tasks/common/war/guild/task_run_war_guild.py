"""Nhận thưởng Đoàn Chiến bằng Template Matching, không sử dụng OCR."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates


_MAX_POLLS = 40
_POLL_INTERVAL = 1.0
_TEMPLATES = (
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
)


def run(worker, account, device, log) -> bool:
    """Nhận thưởng nếu còn; trạng thái đã nhận được xem là hoàn tất."""
    templates = get_templates(_TEMPLATES)
    reward_clicked = False
    receive_prompt_clicked = False
    exit_prompt_clicked = False

    log(f"[{account.display_name}] Bắt đầu kiểm tra trạng thái thưởng Đoàn Chiến.")
    for attempt in range(1, _MAX_POLLS + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang nhận thưởng Đoàn Chiến.")
            return False
        screen = screen_bgr(device)

        summary = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET), account=account, log=log)
        if summary is not None:
            close_summary = match(
                screen,
                templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET),
                account=account,
                log=log,
            )
            if close_summary is not None:
                x, y = click_match(device, close_summary)
                log(f"[{account.display_name}] Đóng bảng tổng kết Đoàn Chiến tại ({x}, {y}).")
            else:
                log(f"[{account.display_name}] Đang ở bảng tổng kết; chờ nút đóng xuất hiện.")
            time.sleep(0.8)
            continue

        already = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG), account=account, log=log)
        if already is not None:
            log(f"[{account.display_name}] Đã nhận thưởng Đoàn Chiến từ trước; không click nhận lặp.")
            return True

        if not reward_clicked:
            reward = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG), account=account, log=log)
            if reward is not None:
                x, y = click_match(device, reward)
                reward_clicked = True
                log(f"[{account.display_name}] Click nút nhận thưởng Đoàn Chiến tại ({x}, {y}).")
                time.sleep(0.8)
                continue

        if reward_clicked and not receive_prompt_clicked:
            prompt = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG), account=account, log=log)
            if prompt is not None:
                x, y = click_match(device, prompt)
                receive_prompt_clicked = True
                log(f"[{account.display_name}] Xác nhận nhận thưởng bằng cách click thông báo tại ({x}, {y}).")
                time.sleep(0.8)
                continue

        if receive_prompt_clicked and not exit_prompt_clicked:
            prompt = match(screen, templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT), account=account, log=log)
            if prompt is not None:
                x, y = click_match(device, prompt)
                exit_prompt_clicked = True
                log(f"[{account.display_name}] Đóng thông báo nhận thưởng tại ({x}, {y}).")
                time.sleep(0.8)
                continue

        log(f"[{account.display_name}] Đang chờ trạng thái đã nhận thưởng (lần {attempt}/{_MAX_POLLS}).")
        time.sleep(_POLL_INTERVAL)

    log(
        f"[{account.display_name}] Không xác nhận được trạng thái đã nhận thưởng sau {_MAX_POLLS} lần; "
        "giữ nguyên trạng thái thất bại để tránh báo hoàn tất sai."
    )
    return False
