"""Tác vụ báo danh trong màn hình Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    """Thực hiện báo danh, không tự mở hoặc đóng màn hình Quân đoàn."""
    return worker._run_guild_screen_task("bao_danh_quan_doan", device, ocr_client)
