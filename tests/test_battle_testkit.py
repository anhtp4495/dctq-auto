from dctq_auto.automation.battle_testkit import (
    BattleMode,
    BattleSnapshot,
    mode_from_config,
    run_mock_battle,
    should_finish_battle,
)


def test_quick_mode_finishes_after_a_win_without_three_flags():
    result = run_mock_battle(
        {"giao_tranh_nhanh_1_co": True, "thoi_gian_giao_tranh": None},
        [
            BattleSnapshot(elapsed_seconds=10, won=False, flags=0),
            BattleSnapshot(elapsed_seconds=20, won=True, flags=1),
        ],
    )

    assert result.finished
    assert result.snapshots_seen == 2
    assert result.reason == "win"


def test_normal_mode_waits_for_win_and_three_flags():
    result = run_mock_battle(
        {"giao_tranh_nhanh_1_co": False, "thoi_gian_giao_tranh": None},
        [
            BattleSnapshot(elapsed_seconds=10, won=True, flags=2),
            BattleSnapshot(elapsed_seconds=20, won=False, flags=3),
            BattleSnapshot(elapsed_seconds=30, won=True, flags=3),
        ],
    )

    assert result.finished
    assert result.snapshots_seen == 3
    assert result.reason == "win_with_three_flags"


def test_time_limit_finishes_at_limit_even_without_a_win():
    result = run_mock_battle(
        {"giao_tranh_nhanh_1_co": False, "thoi_gian_giao_tranh": 15},
        [
            BattleSnapshot(elapsed_seconds=10, won=False, flags=1),
            BattleSnapshot(elapsed_seconds=15, won=False, flags=2),
        ],
    )

    assert result.finished
    assert result.snapshots_seen == 2
    assert result.reason == "time_limit_reached"


def test_time_limit_takes_precedence_when_present():
    mode, limit = mode_from_config(
        {"giao_tranh_nhanh_1_co": True, "thoi_gian_giao_tranh": 30}
    )

    assert mode is BattleMode.TIME_LIMIT
    assert limit == 30


def test_normal_mode_does_not_finish_if_scenario_never_meets_condition():
    result = run_mock_battle(
        {"giao_tranh_nhanh_1_co": False, "thoi_gian_giao_tranh": None},
        [BattleSnapshot(elapsed_seconds=10, won=True, flags=2)],
    )

    assert not result.finished
    assert result.reason == "scenario_exhausted"


def test_time_limit_requires_a_limit_value():
    try:
        should_finish_battle(
            BattleMode.TIME_LIMIT,
            BattleSnapshot(elapsed_seconds=20, won=False, flags=0),
        )
    except ValueError as exc:
        assert "requires time_limit_seconds" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing time limit")
