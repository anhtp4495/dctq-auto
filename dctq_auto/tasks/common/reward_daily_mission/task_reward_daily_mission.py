"""Điều phối quy trình nhận thưởng nhiệm vụ hằng ngày."""

from dctq_auto.config.constants import _STEP_NHAN_THUONG_NHIEM_VU_HANG_NGAY
from dctq_auto.tasks.common.reward_daily_mission import (
    task_close_reward_daily_mission,
    task_open_reward_daily_mission,
    task_run_reward_daily_mission,
)


def pre_reward_daily_mission(steps, log) -> bool:
    """Chỉ tiếp tục khi danh sách steps có yêu cầu nhận thưởng nhiệm vụ hằng ngày."""
    if _STEP_NHAN_THUONG_NHIEM_VU_HANG_NGAY not in steps:
        log("Nhiệm vụ hằng ngày: không có step nhận thưởng trong danh sách; bỏ qua.")
        return False

    log("Nhiệm vụ hằng ngày: tìm thấy step nhận thưởng; bắt đầu thực hiện.")
    return True


def post_reward_daily_mission(steps) -> list[str]:
    """Loại step sau khi quy trình nhận thưởng hoàn tất."""
    if _STEP_NHAN_THUONG_NHIEM_VU_HANG_NGAY in steps:
        steps.remove(_STEP_NHAN_THUONG_NHIEM_VU_HANG_NGAY)
    return steps


def run(worker, account, steps, device, ocr_client, log) -> list[str]:
    """Điều phối mở giao diện, nhận thưởng, đóng giao diện và cập nhật steps."""
    try:
        if not pre_reward_daily_mission(steps, log):
            return steps

        log(f"[{account.display_name}] Bắt đầu quy trình nhận thưởng nhiệm vụ hằng ngày.")
        opened = task_open_reward_daily_mission.run(
            worker, account, device, ocr_client, log
        )
        if not opened:
            log(
                f"[{account.display_name}] Không mở được giao diện nhiệm vụ hằng ngày; "
                "giữ nguyên step."
            )
            return steps

        received = task_run_reward_daily_mission.run(
            worker, account, device, log
        )
        if not received:
            log(
                f"[{account.display_name}] Nhận thưởng nhiệm vụ hằng ngày chưa hoàn tất; "
                "giữ nguyên step."
            )
            return steps

        closed = task_close_reward_daily_mission.run(
            worker, account, device, log
        )
        if not closed:
            log(
                f"[{account.display_name}] Đã nhận thưởng nhiệm vụ hằng ngày nhưng "
                "không đóng được giao diện; vẫn hoàn tất step nhận thưởng."
            )

        return post_reward_daily_mission(steps)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình nhận thưởng nhiệm vụ hằng ngày phát sinh lỗi: {exc}")
        return steps
