"""Điều hướng vào màn hình Quốc chiến.

Tọa độ mở màn hình chưa có trong regions.json của repository hiện tại.
Hàm này chủ động báo lỗi thay vì tự suy đoán tọa độ hoặc click nhầm.
"""


def open_state_war(worker, _device) -> bool:
    worker.log_message.emit(
        "Mở màn hình Quốc chiến: chưa cấu hình tọa độ/nút mở trong regions.json; "
        "hãy mở màn hình Quốc chiến trước khi chạy chiến thuật."
    )
    return False
