"""Smoke tests dùng ADB thật, chỉ kết nối và chụp ảnh; không chạm vào game.

Chỉ chạy khi DCTQ_ADB_SERIAL được thiết lập; nếu không, pytest sẽ skip.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from dctq_auto.adb.client import AdbClient


def _connect_real_device():
    """Kết nối thiết bị ADB được chỉ định bằng DCTQ_ADB_SERIAL."""
    serial = os.getenv("DCTQ_ADB_SERIAL", "").strip()
    if not serial:
        pytest.skip("Đặt DCTQ_ADB_SERIAL để chạy test ADB thật.")

    try:
        return AdbClient(serial=serial).connect()
    except Exception as exc:
        pytest.fail(
            f"Không kết nối được ADB device {serial!r}: {exc}",
            pytrace=True,
        )


def test_real_adb_device_is_online() -> None:
    """Xác nhận thiết bị ADB thật đang online."""
    device = _connect_real_device()
    assert device.get_state() == "device"


def test_real_adb_can_capture_screenshot(tmp_path: Path) -> None:
    """Chụp ảnh thật vào thư mục tạm, không ghi đè ảnh của người dùng."""
    device = _connect_real_device()
    screenshot_path = AdbClient.save_screenshot(device, tmp_path)

    assert screenshot_path.is_file()
    assert screenshot_path.stat().st_size > 0

    with Image.open(screenshot_path) as screenshot:
        assert screenshot.format == "PNG"
        width, height = screenshot.size
        assert width > 0
        assert height > 0
