"""Tác vụ báo danh hằng ngày trong Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    return worker._run_guild_screen_task("bao_danh_quan_doan", device, ocr_client)
