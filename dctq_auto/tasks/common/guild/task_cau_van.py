"""Tác vụ Cầu vận trong màn hình Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    """Thực hiện Cầu vận, không tự mở hoặc đóng màn hình Quân đoàn."""
    return worker._run_guild_screen_task("task_guild_fortune", device, ocr_client)
