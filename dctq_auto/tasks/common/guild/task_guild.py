"""Điều hướng các bước thuộc màn hình Quân đoàn."""

from dctq_auto.tasks.common.guild import (
    task_blessing,
    task_daily_check_in,
    task_donate_rations,
    task_knb,
    task_lucky_bag,
)


_TASKS = (
    ("bao_danh_quan_doan", "Báo danh quân đoàn", task_daily_check_in.run),
    ("task_receive_lucky_bag", "Nhận túi phúc", task_lucky_bag.run),
    ("task_guild_fortune", "Cầu vận quân đoàn (5 lần)", task_blessing.run),
    ("task_donate_rations", "Đóng góp lương thảo", task_donate_rations.run),
    ("task_donate_knb", "Đóng góp KNB", task_knb.run),
)


def run(worker, steps, device, ocr_client, on_complete=None) -> list[str]:
    """Chạy lần lượt các tác vụ Quân đoàn đã chọn, giữ nguyên màn hình."""
    remaining = []
    selected_tasks = [item for item in _TASKS if item[0] in steps]
    for index, (key, label, task_runner) in enumerate(selected_tasks):
        if not worker._wait_if_paused():
            worker.log_message.emit("Đã dừng trước khi chạy tác vụ Quân đoàn.")
            remaining.extend(item[0] for item in selected_tasks[index:])
            break
        success = task_runner(worker, device, ocr_client)
        if success:
            if on_complete:
                on_complete(key, label)
        else:
            remaining.append(key)
            if not worker._wait_if_paused():
                remaining.extend(item[0] for item in selected_tasks[index + 1:])
                break
    return remaining
