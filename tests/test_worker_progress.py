from pathlib import Path

from dctq_auto.gui.workers import BotWorker
from dctq_auto.progress import ProgressStatus


def make_worker():
    return BotWorker(
        serial=None,
        screenshot_dir=Path("."),
        config={},
        mock_mode=True,
    )


def test_worker_emits_unified_and_legacy_overall_progress():
    worker = make_worker()
    legacy = []
    added = []
    changed = []
    worker.progress_changed.connect(lambda *args: legacy.append(args))
    worker.progress_info_added.connect(added.append)
    worker.progress_info_changed.connect(changed.append)

    worker._emit_overall_progress(2, 5, "Đang chạy")

    root = worker.progress_manager.get(worker._progress_root_id)
    assert root is not None
    assert root.current == 2
    assert root.total == 5
    assert root.status is ProgressStatus.RUNNING
    assert added == [root]
    assert changed == [root]
    assert legacy == [(2, 5, "Đang chạy")]


def test_worker_builds_task_tree_and_maps_legacy_statuses():
    worker = make_worker()
    added = []
    legacy = []
    worker.progress_info_added.connect(added.append)
    worker.task_progress_changed.connect(lambda *args: legacy.append(args))

    worker._emit_task_progress("Đăng nhập", "running", 0, 1)
    worker._emit_task_progress("Đăng nhập", "done", 1, 1)

    root = worker.progress_manager.get(worker._progress_root_id)
    children = worker.progress_manager.get_children(root.id)

    assert len(children) == 1
    assert children[0].name == "Đăng nhập"
    assert children[0].parent_id == root.id
    assert children[0].status is ProgressStatus.SUCCESS
    assert children[0].current == 1
    assert len(added) == 2  # root + task
    assert legacy == [
        ("Đăng nhập", "running", 0, 1),
        ("Đăng nhập", "done", 1, 1),
    ]


def test_worker_tracks_clone_account_and_nested_tasks():
    worker = make_worker()
    worker._emit_clone_account_status("Tài khoản A", "running")
    worker._emit_task_progress("Đăng nhập", "running", 0, 1)
    worker._emit_task_progress("Đăng nhập", "done", 1, 1)
    worker._emit_clone_account_result("Tài khoản A", True)

    root = worker.progress_manager.get(worker._progress_root_id)
    account = worker.progress_manager.get_children(root.id)[0]
    task = worker.progress_manager.get_children(account.id)[0]

    assert account.category == "account"
    assert account.status is ProgressStatus.SUCCESS
    assert task.name == "Đăng nhập"
    assert task.status is ProgressStatus.SUCCESS


def test_worker_pause_and_resume_update_root_status():
    worker = make_worker()
    worker._emit_overall_progress(0, 1, "Bắt đầu")

    worker.pause()
    root = worker.progress_manager.get(worker._progress_root_id)
    assert root.status is ProgressStatus.PAUSED

    worker.resume()
    assert root.status is ProgressStatus.RUNNING
