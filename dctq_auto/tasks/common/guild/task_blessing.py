"""Tác vụ Cầu vận (blessing) trong Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    return worker._run_guild_screen_task("task_guild_fortune", device, ocr_client)
