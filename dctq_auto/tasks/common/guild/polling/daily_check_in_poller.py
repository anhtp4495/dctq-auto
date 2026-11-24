"""Poller cho tác vụ Báo danh Quân đoàn."""

from .base_poller import BaseGuildPoller


class DailyCheckInPoller(BaseGuildPoller):
    """Nhận diện trạng thái báo danh theo thứ tự ưu tiên do task cung cấp."""
