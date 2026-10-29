"""Điều hướng các bước thuộc màn hình Quân đoàn."""

from dctq_auto.tasks.common.guild import task_bao_danh, task_cau_van, task_tui_phuc


_TASKS = (
    ("bao_danh_quan_doan", "Báo danh quân đoàn", task_bao_danh.run),
    ("task_receive_lucky_bag", "Nhận túi phúc", task_tui_phuc.run),
    ("task_guild_fortune", "Cầu vận quân đoàn (5 lần)", task_cau_van.run),
)


def run(worker, steps, device, ocr_client, on_complete=None) -> list[str]:
    """Chạy lần lượt các tác vụ Quân đoàn đã chọn.

    Trả về danh sách step thất bại hoặc chưa chạy do người dùng yêu cầu dừng.
    Màn hình Quân đoàn được giữ nguyên giữa các step.
    """
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
