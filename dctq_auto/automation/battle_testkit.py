"""Deterministic battle simulation helpers for testing battle stop conditions.

This module does not issue ADB commands and is not connected to GameBot yet.
It provides a lightweight logic-test harness while real screen recognition and
gameplay actions are still being implemented.
"""

from dataclasses import dataclass
from enum import Enum


class BattleMode(str, Enum):
    QUICK = "quick"
    NORMAL = "normal"
    TIME_LIMIT = "time_limit"


@dataclass(frozen=True)
class BattleSnapshot:
    """One observed point in a simulated battle."""

    elapsed_seconds: int
    won: bool
    flags: int


@dataclass(frozen=True)
class BattleRunResult:
    """Result of running a predefined mock battle timeline."""

    finished: bool
    snapshot: BattleSnapshot | None
    snapshots_seen: int
    reason: str


def mode_from_config(config: dict) -> tuple[BattleMode, int | None]:
    """Translate the GUI's Giao tranh config into a testable battle mode."""
    if config.get("thoi_gian_giao_tranh") is not None:
        return BattleMode.TIME_LIMIT, int(config["thoi_gian_giao_tranh"])
    if config.get("giao_tranh_nhanh_1_co", False):
        return BattleMode.QUICK, None
    return BattleMode.NORMAL, None


def should_finish_battle(
    mode: BattleMode,
    snapshot: BattleSnapshot,
    time_limit_seconds: int | None = None,
) -> tuple[bool, str]:
    """Return whether the selected mode's battle stop condition is satisfied."""
    if mode is BattleMode.TIME_LIMIT:
        if time_limit_seconds is None:
            raise ValueError("Time-limit mode requires time_limit_seconds")
        if snapshot.elapsed_seconds >= time_limit_seconds:
            return True, "time_limit_reached"
        return False, "time_limit_not_reached"

    if not snapshot.won:
        return False, "battle_not_won"

    if mode is BattleMode.QUICK:
        return True, "win"

    if snapshot.flags >= 3:
        return True, "win_with_three_flags"
    return False, "three_flags_not_reached"


def run_mock_battle(
    config: dict,
    timeline: list[BattleSnapshot],
) -> BattleRunResult:
    """Replay scripted observations and stop at the configured condition."""
    mode, time_limit = mode_from_config(config)
    for index, snapshot in enumerate(timeline, start=1):
        finished, reason = should_finish_battle(mode, snapshot, time_limit)
        if finished:
            return BattleRunResult(True, snapshot, index, reason)

    last_snapshot = timeline[-1] if timeline else None
    return BattleRunResult(False, last_snapshot, len(timeline), "scenario_exhausted")
