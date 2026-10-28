"""Registry metadata for Clone Optimize steps."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_STEPS_FILE = Path(__file__).with_name("steps.json")


class CloneStepRegistry:
    """Load step IDs, display labels, config keys, and execution priorities."""

    def __init__(self, steps_file: Path | str = _STEPS_FILE) -> None:
        with Path(steps_file).open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Clone steps JSON must contain a list.")

        self._steps: dict[str, dict[str, Any]] = {}
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Each clone step must be a JSON object.")
            step_id = str(item.get("id", "")).strip()
            display_name = str(item.get("display_name", "")).strip()
            config_key = str(item.get("config_key", "")).strip()
            priority = item.get("priority")

            if not step_id or not display_name or not config_key:
                raise ValueError("Each clone step requires id, display_name, and config_key.")
            if not isinstance(priority, int):
                raise ValueError(f"Clone step {step_id!r} requires an integer priority.")
            if step_id in self._steps:
                raise ValueError(f"Duplicate clone step id: {step_id}")

            self._steps[step_id] = {
                "id": step_id,
                "display_name": display_name,
                "config_key": config_key,
                "priority": priority,
            }

    def get_label(self, step_id: str) -> str:
        """Return the display label for an ID, or the ID itself if unknown."""
        step = self._steps.get(step_id)
        return step["display_name"] if step else step_id

    def get_enabled_steps(self, config: dict[str, Any]) -> list[str]:
        """Return enabled step IDs ordered by priority."""
        enabled = (
            step for step in self._steps.values()
            if bool(config.get(step["config_key"], False))
        )
        return [
            step["id"]
            for step in sorted(enabled, key=lambda item: item["priority"])
        ]

    def get_priority(self, step_id: str) -> int | None:
        """Return a step's priority, or None if the ID is unknown."""
        step = self._steps.get(step_id)
        return step["priority"] if step else None


@lru_cache(maxsize=1)
def get_clone_step_registry() -> CloneStepRegistry:
    """Return a shared registry so step metadata is loaded only once."""
    return CloneStepRegistry()
