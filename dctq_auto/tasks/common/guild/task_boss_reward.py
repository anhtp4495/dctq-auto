"""Điều phối tác vụ nhận thưởng Boss trong màn hình Quân đoàn."""

from dctq_auto.config.constants import _STEP_QUAN_DOAN_NHAN_THUONG_BOSS


def pre_run_boss_reward(steps, log) -> bool:
    """Kiểm tra Clone Optimize có chọn tác vụ nhận thưởng Boss hay không."""
    if _STEP_QUAN_DOAN_NHAN_THUONG_BOSS not in steps:
        log("Nhận thưởng Boss: không có step trong danh sách; bỏ qua.")
        return False

    log("Nhận thưởng Boss: tìm thấy step; bắt đầu thực hiện.")
    return True


def open_boss_reward(worker, account, device, log, screenshot=None) -> bool:
    """Mở giao diện Boss và xác nhận màn hình đích.

    Cần bổ sung template lối vào và template màn hình Boss trước khi bật thao tác.
    """
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi mở giao diện Boss.")
        return False

    log(
        f"[{account.display_name}] Chưa thể mở giao diện Boss: "
        "chưa có template lối vào và màn hình Boss."
    )
    return False


def run_boss_reward(worker, account, device, log) -> bool:
    """Thực hiện nhận thưởng Boss.

    Chưa thao tác khi chưa có template nhận diện màn hình và trạng thái thưởng Boss.
    Điều này tránh click nhầm vào các chức năng khác trong giao diện Quân đoàn.
    """
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Nhận thưởng Boss đã dừng theo yêu cầu.")
        return False

    log(
        f"[{account.display_name}] Chưa triển khai thao tác nhận thưởng Boss: "
        "cần template màn hình Boss và trạng thái có thể nhận thưởng."
    )
    return False


def close_boss_reward(worker, account, device, log) -> bool:
    """Đóng giao diện Boss và xác nhận đã trở về màn hình Quân đoàn."""
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đóng giao diện Boss.")
        return False

    log(
        f"[{account.display_name}] Chưa thể đóng giao diện Boss: "
        "chưa có template màn hình Boss và trạng thái Quân đoàn."
    )
    return False


def post_run_boss_reward(steps, account, log) -> list[str]:
    """Loại step sau khi đã xác nhận nhận thưởng Boss thành công."""
    if _STEP_QUAN_DOAN_NHAN_THUONG_BOSS in steps:
        steps.remove(_STEP_QUAN_DOAN_NHAN_THUONG_BOSS)
    log(f"[{account.display_name}] Hoàn tất tác vụ nhận thưởng Boss Quân đoàn.")
    return steps


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Điều phối tác vụ nhận thưởng Boss theo quy trình pre, run và post."""
    if not pre_run_boss_reward(steps, log):
        return steps

    try:
        if not open_boss_reward(worker, account, device, log, screenshot=screenshot):
            return steps

        if not run_boss_reward(worker, account, device, log):
            return steps

        if not close_boss_reward(worker, account, device, log):
            return steps

        return post_run_boss_reward(steps, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Quy trình nhận thưởng Boss phát sinh lỗi: {exc}")
        return steps
