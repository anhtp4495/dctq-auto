"""Tác vụ nhận Túi phúc trong màn hình Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    """Nhận các Túi phúc, không tự mở hoặc đóng màn hình Quân đoàn."""
    return worker._run_guild_screen_task("task_receive_lucky_bag", device, ocr_client)
