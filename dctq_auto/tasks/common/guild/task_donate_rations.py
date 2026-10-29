"""Tác vụ đóng góp lương thảo trong Quân đoàn."""


def run(worker, device, ocr_client) -> bool:
    """Chạy đóng góp lương thảo khi đã có logic thao tác được khai báo.

    Chưa tự click tọa độ suy đoán: cần tên target/flow được xác nhận trong
    regions.json trước khi tự động hóa thao tác có thể tiêu hao tài nguyên.
    """
    return worker._run_guild_screen_task("task_donate_rations", device, ocr_client)
