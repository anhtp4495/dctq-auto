"""Liệt kê các chiến thuật JSON dùng cho Quốc chiến."""

import json
from pathlib import Path

from dctq_auto.tasks.common.battle.battle_strategies.custom_battle import (
    load_strategy,
)


STRATEGY_DIR = Path(__file__).resolve().parent / "battle_strategies"


def list_battle_strategies() -> list[dict[str, str]]:
    """Liệt kê các kịch bản JSON hợp lệ để hiển thị trên giao diện."""
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    strategies = []
    for path in sorted(
        STRATEGY_DIR.glob("*.json"),
        key=lambda item: item.name.casefold(),
    ):
        try:
            data, _steps = load_strategy(path)
            name = str(
                data.get("display_name") or data.get("name") or path.stem
            ).strip()
            description = str(data.get("description") or "").strip()
            strategies.append({
                "name": name,
                "description": description,
                "path": str(path.resolve()),
            })
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            # Một file hỏng không được làm ảnh hưởng các chiến thuật còn lại.
            continue
    return strategies
