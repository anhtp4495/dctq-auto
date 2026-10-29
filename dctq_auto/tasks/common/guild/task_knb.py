"""Tác vụ đóng góp KNB trong Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    return worker._run_guild_screen_task("task_donate_knb", device, ocr_client)
