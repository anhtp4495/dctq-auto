"""Tác vụ nhận Túi phúc trong Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    return worker._run_guild_screen_task("task_receive_lucky_bag", device, ocr_client)
