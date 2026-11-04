"""Điều hướng đóng màn hình Quốc chiến.

Tọa độ đóng màn hình chưa có trong regions.json của repository hiện tại.
"""


def close_state_war(worker, _device) -> bool:
    worker.log_message.emit(
        "Đóng màn hình Quốc chiến: chưa cấu hình tọa độ nút đóng trong regions.json; "
        "không thực hiện click suy đoán."
    )
    return False
