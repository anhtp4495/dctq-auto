"""Bước Clone Optimize: Nhận lễ bao Quốc Vận trong nhóm Hoạt động - Phúc lợi."""


def chay(worker, device, ocr_client) -> bool:
    """Gọi lại luồng nhận lễ bao Quốc Vận hiện có."""
    return bool(worker._run_receive_quoc_van(device, ocr_client))
