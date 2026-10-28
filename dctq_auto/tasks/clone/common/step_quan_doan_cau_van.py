"""Bước Clone Optimize: Cầu vận quân đoàn."""


def chay(worker, device, ocr_client) -> bool:
    """Mở màn hình quân đoàn rồi thực hiện cầu vận."""
    if not worker._run_enter_guild(device, ocr_client):
        return False
    thanh_cong = bool(worker._run_guild_screen_task("task_guild_fortune", device, ocr_client))
    try:
        ocr_client.tap_ocr_target("close_quan_doan")
        worker._config["_clone_guild_screen_closed"] = True
    except Exception as exc:
        worker.log_message.emit(f"Không đóng được màn hình Quân đoàn sau cầu vận: {exc}")
        return False
    return thanh_cong
