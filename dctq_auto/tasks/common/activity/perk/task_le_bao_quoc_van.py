"""Tác vụ Clone Optimize: Nhận lễ bao Quốc Vận trong nhóm Hoạt động - Phúc lợi."""


def run(worker, device, ocr_client) -> bool:
    """Chạy luồng nhận lễ bao Quốc Vận hiện có."""
    return bool(worker._run_receive_quoc_van(device, ocr_client))
