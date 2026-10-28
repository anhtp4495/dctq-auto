"""Tác vụ Clone Optimize: Báo danh quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    """Mở màn hình quân đoàn rồi thực hiện báo danh."""
    if not worker._run_enter_guild(device, ocr_client):
        return False
    thanh_cong = bool(worker._run_guild_screen_task("bao_danh_quan_doan", device, ocr_client))
    try:
        ocr_client.tap_ocr_target("close_quan_doan")
        worker._config["_clone_guild_screen_closed"] = True
    except Exception as exc:
        worker.log_message.emit(f"Không đóng được màn hình Quân đoàn sau báo danh: {exc}")
        return False
    return thanh_cong
