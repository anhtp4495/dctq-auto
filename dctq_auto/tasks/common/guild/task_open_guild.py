"""Mở màn hình Quân đoàn bằng flow vào Quân đoàn hiện có."""


def run(worker, account, device, ocr_client, log, screenshot=None) -> bool:
    """Mở và xác minh màn hình Quân đoàn."""
    if screenshot is not None:
        log(f"[{account.username}] Bỏ qua screenshot cũ khi mở Quân đoàn; cần ảnh mới để xác minh.")
    return worker._run_enter_guild(device, ocr_client)
