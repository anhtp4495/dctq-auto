"""Các thao tác game dùng chung giữa nhiều tab/nhiệm vụ."""

from dctq_auto.tasks.common.accounts import GameAccount, load_accounts
from dctq_auto.tasks.common.login import SPEC as LOGIN, submit_login_form, verify_login
from dctq_auto.tasks.common.logout import SPEC as LOGOUT, run_logout_flow
from dctq_auto.tasks.common.guild_logistics import run_guild_logistics

__all__ = [
    "GameAccount",
    "load_accounts",
    "LOGIN",
    "LOGOUT",
    "submit_login_form",
    "verify_login",
    "run_logout_flow",
    "run_guild_logistics",
]
