"""Đăng ký thứ tự nhiệm vụ tại một nơi duy nhất.

Ưu tiên: Điểm danh -> Báo danh quân đoàn -> nhiệm vụ hằng ngày khác
-> Giao tranh -> Tranh bá. Thiết lập mưu binh thuộc tab khác.
"""
from .base import TaskSpec
from .daily_check_in import SPEC as DAILY_CHECK_IN
from .guild_check_in import SPEC as GUILD_CHECK_IN
from .knb_contribution import SPEC as KNB_CONTRIBUTION
from .territory_exploration import SPEC as TERRITORY_EXPLORATION
from .glass_tower import SPEC as GLASS_TOWER
from .battle import SPEC as BATTLE
from .championship import SPEC as CHAMPIONSHIP

TASK_REGISTRY: tuple[TaskSpec, ...] = (
    DAILY_CHECK_IN,
    GUILD_CHECK_IN,
    KNB_CONTRIBUTION,
    TERRITORY_EXPLORATION,
    GLASS_TOWER,
    BATTLE,
    CHAMPIONSHIP,
)


def get_enabled_tasks(config: dict) -> list[tuple[TaskSpec, int]]:
    """Lấy các nhiệm vụ được bật theo thứ tự ưu tiên."""
    return [
        (spec, spec.get_count(config))
        for spec in TASK_REGISTRY
        if spec.is_enabled(config)
    ]
