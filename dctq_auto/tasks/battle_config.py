"""Cấu hình dùng chung cho các chế độ chiến đấu."""

from dataclasses import dataclass
from typing import Literal


BattleMode = Literal["fast", "normal", "time_limit"]


@dataclass(frozen=True, slots=True)
class BattleConfig:
    """Các tùy chọn số trận và cách kết thúc mỗi trận."""

    battle_count: int = 15
    mode: BattleMode = "time_limit"
    time_limit_seconds: int = 45

    def __post_init__(self) -> None:
        if self.battle_count < 1:
            raise ValueError("battle_count phải lớn hơn hoặc bằng 1.")
        if self.mode not in ("fast", "normal", "time_limit"):
            raise ValueError(f"Chế độ chiến đấu không hợp lệ: {self.mode!r}.")
        if self.time_limit_seconds < 1:
            raise ValueError("time_limit_seconds phải lớn hơn hoặc bằng 1.")
