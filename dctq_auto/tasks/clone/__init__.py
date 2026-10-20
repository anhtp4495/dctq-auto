"""Các nhiệm vụ thao tác lần lượt trên danh sách tài khoản clone."""

from dctq_auto.tasks.common.accounts import GameAccount as CloneAccount, load_accounts
from dctq_auto.tasks.clone.login import SPEC as LOGIN
from dctq_auto.tasks.clone.logout import SPEC as LOGOUT
from dctq_auto.tasks.clone.daily_check_in import SPEC as DAILY_CHECK_IN
from dctq_auto.tasks.clone.guild_check_in import SPEC as GUILD_CHECK_IN
from dctq_auto.tasks.clone.receive_lucky_bag import SPEC as RECEIVE_LUCKY_BAG

TASKS = (LOGIN, DAILY_CHECK_IN, GUILD_CHECK_IN, RECEIVE_LUCKY_BAG, LOGOUT)

__all__ = ["CloneAccount", "load_accounts", "TASKS"]
