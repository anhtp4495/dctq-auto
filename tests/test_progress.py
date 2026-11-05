from datetime import datetime

import pytest

from dctq_auto.progress import (
    ProgressCategory,
    ProgressInfo,
    ProgressManager,
    ProgressStatus,
)


def test_progress_info_has_unique_id_and_default_state():
    first = ProgressInfo(name="Clone", category="standalone")
    second = ProgressInfo(name="Clone", category="standalone")

    assert first.id != second.id
    assert first.status is ProgressStatus.PENDING
    assert first.current == 0
    assert first.total == 1
    assert first.parent_id is None


def test_progress_manager_supports_parent_child_tree():
    manager = ProgressManager()
    root = manager.add(ProgressInfo(name="Clone", category="standalone"))
    account = manager.add(
        ProgressInfo(
            name="Tài khoản A",
            category="account",
            parent_id=root.id,
            account="A",
        )
    )

    assert manager.get(root.id) is root
    assert manager.get_children(root.id) == [account]
    assert manager.get_children(account.id) == []


def test_progress_manager_updates_status_and_timestamps():
    manager = ProgressManager()
    item = manager.add(ProgressInfo(name="Đăng nhập", category="standalone"))

    manager.update(item.id, status="running", message="Đang đăng nhập")
    assert item.status is ProgressStatus.RUNNING
    assert isinstance(item.started_at, datetime)
    assert item.finished_at is None

    manager.update(item.id, status="success", current=1, message="Hoàn thành")
    assert item.status is ProgressStatus.SUCCESS
    assert isinstance(item.finished_at, datetime)


def test_progress_manager_rejects_missing_parent_and_invalid_counts():
    manager = ProgressManager()
    with pytest.raises(KeyError):
        manager.add(
            ProgressInfo(name="Child", category="standalone", parent_id="missing")
        )

    with pytest.raises(ValueError):
        ProgressInfo(name="Invalid", category="standalone", current=2, total=1)


def test_progress_manager_rejects_duplicate_ids_and_unknown_updates():
    manager = ProgressManager()
    item = manager.add(ProgressInfo(name="Task", category="standalone"))

    with pytest.raises(ValueError):
        manager.add(item)

    with pytest.raises(TypeError):
        manager.update(item.id, unknown_field=True)


def test_progress_manager_reset_clears_items():
    manager = ProgressManager()
    item = manager.add(ProgressInfo(name="Task", category="standalone"))

    manager.reset()

    assert manager.get(item.id) is None
    assert manager.get_all() == []


def test_progress_category_is_limited_to_account_and_standalone():
    account = ProgressInfo(name="Tài khoản A", category="account")
    standalone = ProgressInfo(name="Đăng nhập", category="standalone")

    assert account.category is ProgressCategory.ACCOUNT
    assert standalone.category is ProgressCategory.STANDALONE

    with pytest.raises(ValueError):
        ProgressInfo(name="Invalid", category="task")


def test_progress_manager_rejects_invalid_category_updates():
    manager = ProgressManager()
    item = manager.add(ProgressInfo(name="Task", category="standalone"))

    with pytest.raises(ValueError):
        manager.update(item.id, category="task")

    assert item.category is ProgressCategory.STANDALONE
