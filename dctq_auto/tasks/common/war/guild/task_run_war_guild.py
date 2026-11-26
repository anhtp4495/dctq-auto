"""Điều phối nghiệp vụ nhận thưởng và bổ sung phòng thủ Đoàn Chiến."""

import time
from datetime import datetime

from dctq_auto.config.constants import (
    _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG,
    _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_QUYEN_GOP,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, screen_bgr
from dctq_auto.tasks.common.war.guild.polling import (
    DefenseReinforcementPoller,
    GuildWarRewardPoller,
)
from dctq_auto.vision.template_store import get_templates


_POLL_INTERVAL = 0.8
_POLL_TIMEOUT_SECONDS = 180
_MAX_REWARD_NOT_FOUND = 3
_MAX_CONTRIBUTIONS = 30

_REWARD_TEMPLATES = (
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_TAM_QUAN_DONG_TONG_KET,
)

_MAIN_SCREEN = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_MAN_HINH_CHINH
_CONTRIBUTE = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_QUYEN_GOP
_CONFIRM = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_XAC_NHAN
_RESOURCES_EXHAUSTED = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_HET_TAI_NGUYEN
_EXIT = _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_QUYEN_GOP_PHONG_THU_THOAT


def _defense_reinforcement_is_due(now: datetime) -> bool:
    """Thứ Năm từ 07:00 đến hết thứ Sáu 23:00."""
    if now.weekday() == 3:
        return now.hour >= 7
    if now.weekday() == 4:
        return (now.hour, now.minute) <= (23, 0)
    return False


def _run_reward(worker, account, device, log) -> bool:
    """Nhận thưởng Đoàn Chiến và Tam Quân bằng Reward Poller."""
    poller = GuildWarRewardPoller()
    templates = get_templates(_REWARD_TEMPLATES)
    not_found_count = 0
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    log(f"[{account.display_name}] Bắt đầu kiểm tra trạng thái thưởng Đoàn Chiến.")
    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi đang nhận thưởng Đoàn Chiến.")
            return False

        screen = screen_bgr(device)
        observation = poller.poll(screen, templates, _REWARD_TEMPLATES, account, log)
        state = observation["state"]

        if state == "reward_claimed":
            log(f"[{account.display_name}] Đã nhận thưởng Đoàn Chiến.")
            return True

        if state == "not_found":
            not_found_count += 1
            log(
                f"[{account.display_name}] Không nhận diện được trạng thái nhận thưởng "
                f"(lần {not_found_count}/{_MAX_REWARD_NOT_FOUND})."
            )
            if not_found_count >= _MAX_REWARD_NOT_FOUND:
                return False
        else:
            not_found_count = 0
            match_result = observation.get("match")

            if state == "summary_screen":
                close_observation = poller.poll(
                    screen,
                    templates,
                    (_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,),
                    account,
                    log,
                )
                match_result = close_observation.get("match")
                if match_result is None:
                    log(f"[{account.display_name}] Chưa tìm thấy nút đóng bảng tổng kết Đoàn Chiến.")
                    time.sleep(_POLL_INTERVAL)
                    continue
            elif state == "close_summary":
                pass

            if match_result is not None:
                x, y = click_match(device, match_result)
                log(
                    f"[{account.display_name}] Click [{observation['template_name']}] "
                    f"tại ({x}, {y}) để tiếp tục xử lý thưởng."
                )

        time.sleep(_POLL_INTERVAL)

    log(
        f"[{account.display_name}] Nhận thưởng Đoàn Chiến quá thời gian polling "
        f"{_POLL_TIMEOUT_SECONDS} giây."
    )
    return False


def _run_defense_reinforcement(worker, account, device, log) -> bool:
    """Quyên góp phòng thủ tối đa 30 lần hoặc dừng ngay khi hết tài nguyên."""
    poller = DefenseReinforcementPoller()
    phase = "prepare"
    contribution_count = 0
    template_names = (_MAIN_SCREEN,)
    templates = get_templates(template_names)
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    log(f"[{account.display_name}] Bắt đầu bổ sung phòng thủ Đoàn Chiến.")
    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Bổ sung phòng thủ đã dừng theo yêu cầu.")
            return False

        screen = screen_bgr(device)
        observation = poller.poll(screen, templates, template_names, account, log)
        state = observation["state"]

        if phase == "prepare":
            if state == "main_screen":
                phase = "contribute"
                template_names = (_RESOURCES_EXHAUSTED, _CONFIRM, _CONTRIBUTE)
                templates = get_templates(template_names)
                log(f"[{account.display_name}] Đã xác nhận màn hình Chuẩn bị - Bổ sung phòng thủ.")
        elif phase == "contribute":
            if state == "resources_exhausted":
                phase = "close"
                template_names = (_EXIT, _MAIN_SCREEN)
                templates = get_templates(template_names)
                log(f"[{account.display_name}] Đã hết tài nguyên; dừng quyên góp và chuyển sang thoát.")
            elif state == "contribute":
                x, y = click_match(device, observation["match"])
                contribution_count += 1
                log(
                    f"[{account.display_name}] Quyên góp phòng thủ "
                    f"({contribution_count}/{_MAX_CONTRIBUTIONS}) tại ({x}, {y})."
                )
                if contribution_count >= _MAX_CONTRIBUTIONS:
                    phase = "close"
                    template_names = (_EXIT, _MAIN_SCREEN)
                    templates = get_templates(template_names)
                    log(f"[{account.display_name}] Đã đủ {_MAX_CONTRIBUTIONS} lượt quyên góp; chuyển sang thoát.")
            elif state == "confirm":
                x, y = click_match(device, observation["match"])
                log(f"[{account.display_name}] Click xác nhận quyên góp tại ({x}, {y}).")
        elif phase == "close":
            if state == "exit":
                x, y = click_match(device, observation["match"])
                log(f"[{account.display_name}] Click thoát màn hình bổ sung phòng thủ tại ({x}, {y}).")
            elif state == "main_screen":
                log(
                    f"[{account.display_name}] Đã xác nhận quay lại màn hình Chuẩn bị - "
                    "Bổ sung phòng thủ; hoàn tất."
                )
                return True

        time.sleep(_POLL_INTERVAL)

    log(
        f"[{account.display_name}] Bổ sung phòng thủ quá thời gian polling "
        f"{_POLL_TIMEOUT_SECONDS} giây; giữ nguyên step."
    )
    return False


def run(worker, account, steps: list[str], device, log) -> list[str]:
    """Chạy nghiệp vụ nhận thưởng và bổ sung phòng thủ trong màn hình Đoàn Chiến."""
    now = datetime.now()
    if _STEP_CHIEN_TRANH_QUAN_DOAN_NHAN_THUONG in steps and now.weekday() in (0, 1):
        if _run_reward(worker, account, device, log):
            log(f"[{account.display_name}] Đã hoàn tất nhận thưởng Đoàn Chiến.")

    if (
        _STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU in steps
        and _defense_reinforcement_is_due(now)
    ):
        if _run_defense_reinforcement(worker, account, device, log):
            steps.remove(_STEP_CHIEN_TRANH_QUAN_DOAN_BO_SUNG_PHONG_THU)
            log(f"[{account.display_name}] Đã hoàn tất Bổ sung phòng thủ Đoàn Chiến.")
    return steps
