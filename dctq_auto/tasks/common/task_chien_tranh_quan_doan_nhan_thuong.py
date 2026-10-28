"""Tác vụ Clone Optimize: Nhận thưởng Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    """Chạy luồng nhận thưởng Đoàn Chiến hiện có."""
    from dctq_auto.tasks.reward_weekly_doan_chien import run_reward_weekly_doan_chien

    result = run_reward_weekly_doan_chien(worker, device, 0, 1)
    return result is not None
