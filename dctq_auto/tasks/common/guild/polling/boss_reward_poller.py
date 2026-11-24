"""Poller cho tác vụ nhận thưởng Boss Quân đoàn."""

from .base_poller import BaseGuildPoller


class BossRewardPoller(BaseGuildPoller):
    """Nhận diện các trạng thái điều hướng và nhận thưởng Boss."""
