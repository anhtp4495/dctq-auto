"""Tương thích ngược; bộ đọc tài khoản đã chuyển sang tasks.common."""

from dctq_auto.tasks.common.accounts import GameAccount as CloneAccount
from dctq_auto.tasks.common.accounts import load_accounts

__all__ = ["CloneAccount", "load_accounts"]
