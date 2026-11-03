"""Tương thích ngược cho các import BattleConfig cũ.

Cấu hình chiến đấu hiện được định nghĩa tại
:mod:`dctq_auto.tasks.common.battle.battle_config`.
"""

from dctq_auto.tasks.common.battle.battle_config import (
    BattleConfig,
    BattleMode,
    get_battle_config,
)

__all__ = ["BattleConfig", "BattleMode", "get_battle_config"]
