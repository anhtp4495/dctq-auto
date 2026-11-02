"""Poller cho chế độ Giao Tranh bình thường."""

from .base_poller import BasePoller


class NormalPoller(BasePoller):
    """Chỉ quan sát trạng thái trận; không tự kết thúc theo thời gian."""
