"""Background workers for GUI actions."""

import shlex
from dataclasses import replace
import time
from pathlib import Path
from types import SimpleNamespace
from threading import Event
from PySide6.QtCore import QThread, Signal

from dctq_auto.adb.client import AdbClient
from dctq_auto.automation.battle_testkit import BattleSnapshot, run_mock_battle
from dctq_auto.tasks.registry import get_enabled_tasks
from dctq_auto.tasks.common.accounts import load_accounts
from dctq_auto.tasks.activity.worker import ActivityWorkerMixin
from dctq_auto.progress import ProgressInfo, ProgressManager, ProgressStatus


class BotWorker(
    ActivityWorkerMixin,
    QThread,
):
    """Run test battle logic or the current ADB preparation flow."""

    log_message = Signal(str)
    progress_changed = Signal(int, int, str)
    task_progress_changed = Signal(str, str, int, int)
    task_progress_item_added = Signal(str, int)
    clone_account_result = Signal(str, bool)
    clone_account_status = Signal(str, str)
    progress_info_added = Signal(object)
    progress_info_changed = Signal(object)

    def __init__(
        self,
        serial: str | None,
        screenshot_dir: Path,
        config: dict,
        mock_mode: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._serial = serial
        self._screenshot_dir = screenshot_dir
        self._config = config
        self._mock_mode = mock_mode
        self._resume_event = Event()
        self._resume_event.set()
        self._progress_total = 1
        self._progress_completed = 0
        self.progress_manager = ProgressManager()
        self._progress_root_id: str | None = None
        self._current_process_ids: dict[str, str] = {}
        self._progress_items_by_key: dict[tuple[str, str], str] = {}
        self._progress_accounts: dict[str, str] = {}
        self._active_progress_account_id: str | None = None
        self._progress_failed = False
        self._clone_progress_steps_only = False
        self._clone_progress_force_emit = False

    def _ensure_progress_root(self) -> ProgressInfo:
        """Create the root item lazily so each worker run owns one progress tree."""
        if self._progress_root_id is None:
            root = self.progress_manager.add(
                ProgressInfo(name="Tiến trình", category="standalone")
            )
            self._progress_root_id = root.id
            self.progress_info_added.emit(replace(root))
        root = self.progress_manager.get(self._progress_root_id)
        assert root is not None
        return root

    def _emit_progress_item(self, item: ProgressInfo) -> None:
        self.progress_info_changed.emit(replace(item))

    def SearchProcessInfo(self, process_id: str) -> ProgressInfo | None:
        """Find a registered progress item by its ID."""
        return self.progress_manager.get(process_id)

    def UpdateProcessMessage(self, process_id: str, message: str) -> bool:
        """Update an existing progress item's message and notify the GUI."""
        item = self.SearchProcessInfo(process_id)
        if item is None:
            return False

        item = self.progress_manager.update(item.id, message=message)
        self._emit_progress_item(item)
        return True

    def UpdateProcessStatus(
        self, process_id: str, status: ProgressStatus | str
    ) -> bool:
        """Update an existing progress item's status and notify the GUI."""
        item = self.SearchProcessInfo(process_id)
        if item is None:
            return False

        item = self.progress_manager.update(item.id, status=status)
        self._emit_progress_item(item)
        return True

    def UpdateProcessInfo(
        self, process_id: str, current: int, total: int,
    ) -> bool:
        """Update an existing progress item's status and notify the GUI."""
        item = self.SearchProcessInfo(process_id)
        if item is None:
            return False

        item = self.progress_manager.update(item.id, current=max(0, current), total=max(0, total))
        self._emit_progress_item(item)
        return True

    def _emit_overall_progress(
        self, completed: int, total: int, message: str
    ) -> None:
        """Update the unified root progress and retain the legacy GUI signal."""
        root = self._ensure_progress_root()
        changes = {
            "current": max(0, completed),
            "total": max(0, total),
            "message": message,
        }
        if root.status in (ProgressStatus.PENDING, ProgressStatus.PAUSED):
            changes["status"] = ProgressStatus.RUNNING
        updated = self.progress_manager.update(root.id, **changes)
        self._emit_progress_item(updated)
        self.progress_changed.emit(completed, total, message)

    def _get_progress_task_name(self, name: str) -> str:
        """Remove the active Clone account prefix from a child task label."""
        account_id = self._active_progress_account_id
        if account_id is None:
            return name
        account = self.progress_manager.get(account_id)
        if account is None:
            return name
        account_name = account.account or account.name
        prefix = f"{account_name} - "
        return name[len(prefix):] if name.startswith(prefix) else name

    def UpdateOrCreateProcessProgress(
        self,
        name: str,
        status: ProgressStatus | str,
        current: int,
        total: int,
        message: str | None = None,
        parent_id: str | None = None,
    ) -> str:
        """Update an existing progress item or create it, returning its ID."""
        if parent_id is None:
            parent_id = self._active_progress_account_id or self._ensure_progress_root().id

        task_name = self._get_progress_task_name(name)
        key = (parent_id, task_name)
        progress_id = self._progress_items_by_key.get(key)

        status_map = {
            "pending": ProgressStatus.PENDING,
            "running": ProgressStatus.RUNNING,
            "done": ProgressStatus.SUCCESS,
            "success": ProgressStatus.SUCCESS,
            "failed": ProgressStatus.FAILED,
            "ignored": ProgressStatus.SKIPPED,
            "skipped": ProgressStatus.SKIPPED,
            "stopped": ProgressStatus.STOPPED,
        }
        progress_status = (
            status_map.get(status, ProgressStatus.RUNNING)
            if isinstance(status, str) else status
        )
        progress_message = task_name if message is None else message
        changes = {
            "status": progress_status,
            "current": max(0, current),
            "total": max(0, total),
            "message": progress_message,
            "error": (
                "Tác vụ thất bại"
                if progress_status == ProgressStatus.FAILED else None
            ),
        }

        if progress_id is None:
            item = self.progress_manager.add(
                ProgressInfo(
                    id=f"task-{len(self._progress_items_by_key) + 1}",
                    parent_id=parent_id,
                    name=task_name,
                    category="standalone",
                    **changes,
                )
            )
            self._progress_items_by_key[key] = item.id
            self.progress_info_added.emit(replace(item))
        else:
            item = self.progress_manager.update(progress_id, **changes)
            self._emit_progress_item(item)

        return item.id

    def _emit_task_progress(
        self, name: str, state: str, current: int, total: int,
        message: str | None = None,
    ) -> None:
        """Update a task node and retain the existing task progress signal."""
        if self._clone_progress_steps_only and not self._clone_progress_force_emit:
            self.task_progress_changed.emit(name, state, current, total)
            return

        self.UpdateOrCreateProcessProgress(
            name=name,
            status=state,
            current=current,
            total=total,
            message=message,
        )
        self.task_progress_changed.emit(name, state, current, total)

        # Keep the Clone account row informative while its child task runs.
        account_id = self._active_progress_account_id
        if account_id is not None:
            account_message = {
                "running": f"Đang chạy: {name}",
                "done": f"Hoàn thành: {name}",
                "success": f"Hoàn thành: {name}",
                "failed": f"Thất bại: {name}",
                "ignored": f"Đã bỏ qua: {name}",
                "skipped": f"Đã bỏ qua: {name}",
                "stopped": f"Đã dừng: {name}",
            }.get(state, f"Đang xử lý: {name}")
            account_item = self.progress_manager.get(account_id)
            if account_item is not None:
                account_item = self.progress_manager.update(
                    account_id, message=account_message
                )
                self._emit_progress_item(account_item)

    def _emit_clone_step_progress(
        self, name: str, state: str, current: int, total: int
    ) -> None:
        """Emit one selected Clone step while suppressing internal progress nodes."""
        previous = self._clone_progress_force_emit
        self._clone_progress_force_emit = True
        try:
            self._emit_task_progress(name, state, current, total)
        finally:
            self._clone_progress_force_emit = previous

    def _add_task_progress_item(self, name: str, total: int) -> None:
        """Register a pending task row while preserving the legacy list signal."""
        if self._clone_progress_steps_only:
            self.task_progress_item_added.emit(name, total)
            return
        root = self._ensure_progress_root()
        parent_id = self._active_progress_account_id or root.id
        task_name = self._get_progress_task_name(name)
        key = (parent_id, task_name)
        progress_id = self._progress_items_by_key.get(key)
        if progress_id is None:
            item = self.progress_manager.add(
                ProgressInfo(
                    id=f"task-{len(self._progress_items_by_key) + 1}",
                    parent_id=parent_id,
                    name=task_name,
                    category="standalone",
                    current=0,
                    total=max(0, total),
                    message=task_name,
                )
            )
            self._progress_items_by_key[key] = item.id
            self.progress_info_added.emit(replace(item))
        self.task_progress_item_added.emit(name, total)

    def _emit_clone_account_status(self, display_name: str, state: str) -> None:
        """Represent each Clone account as a child of the run progress."""
        root = self._ensure_progress_root()
        account_id = self._progress_accounts.get(display_name)
        status = (
            ProgressStatus.RUNNING if state == "running"
            else ProgressStatus.SKIPPED if state == "disabled"
            else ProgressStatus.PENDING
        )
        if account_id is None:
            item = self.progress_manager.add(
                ProgressInfo(
                    name=display_name,
                    category="account",
                    parent_id=root.id,
                    account=display_name,
                    status=status,
                    message=state,
                )
            )
            self._progress_accounts[display_name] = item.id
            self.progress_info_added.emit(item)
            account_id = item.id
        else:
            item = self.progress_manager.update(
                account_id, status=status, message=state
            )
            self._emit_progress_item(item)
        if state == "running":
            self._active_progress_account_id = account_id
        self.clone_account_status.emit(display_name, state)

    def _emit_clone_account_result(
        self, display_name: str, succeeded: bool
    ) -> None:
        account_id = self._progress_accounts.get(display_name)
        if account_id is not None:
            item = self.progress_manager.update(
                account_id,
                status=(
                    ProgressStatus.SUCCESS if succeeded
                    else ProgressStatus.FAILED
                ),
                current=1 if succeeded else 0,
                total=1,
                message="Hoàn thành" if succeeded else "Thất bại",
                error=None if succeeded else "Tài khoản xử lý thất bại",
            )
            self._emit_progress_item(item)
        if self._active_progress_account_id == account_id:
            self._active_progress_account_id = None
        self.clone_account_result.emit(display_name, succeeded)

    def _set_progress_root_message(self, message: str) -> None:
        """Update the root row's message without changing overall progress counts."""
        root = self._ensure_progress_root()
        item = self.progress_manager.update(root.id, message=message)
        self._emit_progress_item(item)

    def _set_root_status(self, status: ProgressStatus, message: str) -> None:
        if self._progress_root_id is None:
            return
        item = self.progress_manager.update(
            self._progress_root_id, status=status, message=message
        )
        self._emit_progress_item(item)

    def pause(self) -> None:
        self._resume_event.clear()
        self._set_root_status(ProgressStatus.PAUSED, "Đang tạm dừng")

    def resume(self) -> None:
        self._resume_event.set()
        self._set_root_status(ProgressStatus.RUNNING, "Đang tiếp tục")


    def _wait_if_paused(self) -> bool:
        while not self._resume_event.wait(0.1):
            if self.isInterruptionRequested():
                return False
        return not self.isInterruptionRequested()

    def _mock_tick(self, message: str) -> bool:
        """Log one simulated action, respecting pause and stop requests."""
        if not self._wait_if_paused():
            self.log_message.emit("Đã dừng theo yêu cầu.")
            return False
        time.sleep(0.12)
        if self.isInterruptionRequested():
            self.log_message.emit("Đã dừng theo yêu cầu.")
            return False
        self.log_message.emit(f"{message}")
        return True

    @staticmethod
    def _estimated_task_seconds(task: str, config: dict) -> int:
        """Ước tính thời lượng để phân bổ tiến trình tổng theo thời gian."""
        if task == "Giao tranh":
            return max(1, int(config.get("thoi_gian_giao_tranh") or 180))
        if task == "Tranh bá":
            return max(1, int(config.get("thoi_gian_tranh_ba") or 180))
        return 30

    def _emit_mock_progress(self, partial_units: int, status: str) -> None:
        value = min(self._progress_total, self._progress_completed + max(0, partial_units))
        self._emit_overall_progress(value, self._progress_total, status)

    def _simulate_battles(self, task: str, count: int, required_flags: int,
                          time_limit: int | None) -> bool:
        for number in range(1, count + 1):
            elapsed = 0
            while True:
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return False
                time.sleep(0.12)
                elapsed += 3
                won = time_limit is None and elapsed >= 9
                flags = min(max(elapsed // 3 - 1, 0), required_flags)
                if task == "Giao tranh":
                    snapshot = BattleSnapshot(elapsed, won, flags)
                    result = run_mock_battle(self._config, [snapshot])
                    finished, reason = result.finished, result.reason
                elif time_limit is not None:
                    finished = elapsed >= time_limit
                    reason = "time_limit_reached" if finished else "time_limit_not_reached"
                elif not won:
                    finished, reason = False, "battle_not_won"
                elif flags >= required_flags:
                    finished, reason = True, f"win_with_{required_flags}_flags"
                else:
                    finished, reason = False, "flags_not_reached"
                if not self._mock_tick(
                    f"{task} {number}/{count}: t={elapsed}s, "
                    f"{'thắng' if won else 'chưa thắng'}, {flags} cờ."
                ):
                    return False
                # Overall progress advances only when a battle is completed.
                self._emit_mock_progress(0, f"{task}: trận {number}/{count}")
                if finished:
                    if not self._mock_tick(f"Kết thúc {task} {number}: {reason}."):
                        return False
                    self._emit_task_progress(task, "running", number, count)
                    self._progress_completed += 1
                    self._emit_mock_progress(0, f"Hoàn thành lượt {self._progress_completed}/{self._progress_total}: {task} {number}/{count}")
                    break
        return True

    def _run_mock(self) -> None:
        """Simulate configured tasks and update progress without connecting to ADB."""
        if self._config.get("state_war_mode"):
            from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUOC_CHIEN
            from dctq_auto.tasks.common.state_war.task_state_war import pre_state_war
            from dctq_auto.tasks.common.state_war.task_run_state_war import (
                get_battle_step_progress_label,
                load_battle_strategy,
            )
            strategy_path = self._config.get("state_war_strategy_path", "")
            selected_steps = [_STEP_CHIEN_TRANH_QUOC_CHIEN]
            if not pre_state_war(
                selected_steps,
                strategy_path,
                self.log_message.emit,
                add_progress_item=self._add_task_progress_item,
            ):
                self._emit_task_progress(
                    "Triển khai chiến thuật Quốc chiến", "ignored", 0, 1
                )
                return
            try:
                data, steps = load_battle_strategy(strategy_path)
            except Exception as exc:
                self.log_message.emit(f"[Chạy thử] Quốc chiến: chiến thuật không hợp lệ: {exc}")
                self._emit_task_progress(
                    "Triển khai chiến thuật Quốc chiến", "failed", 0, 1
                )
                return
            name = str(data.get("name") or "Chiến thuật")
            total = len(steps)
            self._emit_overall_progress(0, total, f"Chạy thử Quốc chiến: {name}")
            self._emit_task_progress("Bắt đầu", "running", 0, 1)
            self._emit_task_progress("Bắt đầu", "done", 1, 1)
            for index, step in enumerate(steps, start=1):
                progress_label = get_battle_step_progress_label(step, index)
                self._emit_task_progress(
                    progress_label, "running", 0, 1
                )
                if not self._mock_tick(
                    f"[Chạy thử] Quốc chiến {name}: {step['type']} ({index}/{total})."
                ):
                    self._emit_task_progress(
                        progress_label, "stopped", 0, 1
                    )
                    return
                self._emit_task_progress(
                    progress_label, "done", 1, 1
                )
                self._emit_overall_progress(
                    index, total, f"Chạy thử Quốc chiến: {index}/{total}"
                )
            self._emit_task_progress("Kết thúc", "running", 0, 1)
            self._emit_task_progress("Kết thúc", "done", 1, 1)
            self.log_message.emit(
                f"[Chạy thử] Hoàn tất mô phỏng chiến thuật Quốc chiến '{name}'. Không gửi lệnh ADB."
            )
            return
        if self._config.get("strategy_mode"):
            self._set_progress_root_message("Đã vượt ải 0")
            self._emit_task_progress("Chiến đấu", "pending", 0, 0)
            self._emit_task_progress("Nhận thưởng", "pending", 0, 0)

            self._emit_task_progress("Chiến đấu", "running", 0, 0)
            if not self._mock_tick("[Chạy thử] Mưu Binh: chiến đấu."):
                self._emit_task_progress("Chiến đấu", "stopped", 0, 0)
                return

            self._emit_task_progress("Nhận thưởng", "running", 0, 0)
            if not self._mock_tick("[Chạy thử] Mưu Binh: nhận thưởng."):
                self._emit_task_progress("Nhận thưởng", "stopped", 0, 0)
                return

            self._set_progress_root_message("Đã vượt ải 1")
            self._emit_task_progress("Chiến đấu", "success", 0, 0)
            self._emit_task_progress("Nhận thưởng", "success", 0, 0)
            self.log_message.emit(
                "[Chạy thử] Hoàn tất mô phỏng Mưu Binh: đã vượt 1 ải. "
                "Không gửi lệnh ADB."
            )
            return
        if self._config.get("clone_mode"):
            self._run_clone_mock()
            return
        tasks = [(spec.label, count) for spec, count in get_enabled_tasks(self._config)]

        # Count every configured run, not estimated seconds or task groups.
        total = sum(count for _task, count in tasks)
        if total == 0:
            self.log_message.emit("Không có nhiệm vụ nào được chọn.")
            self._emit_overall_progress(0, 0, "Không có nhiệm vụ được chọn")
            return

        self._progress_total = total
        self._progress_completed = 0
        self._emit_overall_progress(0, self._progress_total, "Bắt đầu")
        self.log_message.emit(
            f"Bắt đầu chạy thử {len(tasks)} nhóm nhiệm vụ, tổng cộng {total} lượt. "
            f"Không kết nối ADB và không điều khiển game."
        )
        for task, count in tasks:
            self._emit_task_progress(task, "running", 0, count)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if task in ("Giao tranh", "Tranh bá"):
                is_giao_tranh = task == "Giao tranh"
                if is_giao_tranh:
                    if self._config.get("ha_chien_cong"):
                        if not self._mock_tick(
                            f"Hạ chiến công: chạy thử mục tiêu {self._config.get('chien_cong', 200)}."
                        ):
                            return
                    elif self._config.get("chon_nha_npc"):
                        if not self._mock_tick("Chọn nhà NPC: chạy thử chọn mục tiêu."):
                            return
                    if self._config.get("su_dung_canh_bat_tran"):
                        if not self._mock_tick("Canh Bát Trân: chạy thử kích hoạt."):
                            return
                    flags = 1 if self._config.get("giao_tranh_nhanh_1_co") else 3
                    limit = self._config.get("thoi_gian_giao_tranh")
                else:
                    if self._config.get("mua_luot_knb"):
                        if not self._mock_tick("Tranh bá: chạy thử mua lượt bằng KNB."):
                            return
                    flags = int(self._config.get("tranh_ba_fast_mode", 4))
                    limit = self._config.get("thoi_gian_tranh_ba")
                if not self._simulate_battles(task, count, flags, limit):
                    return
            else:
                for number in range(1, count + 1):
                    if task == "Nhiệm vụ Lưu Ly Tháp" and self._config.get("luu_ly_thap_knb"):
                        if not self._mock_tick(
                            f"{task}: chạy thử mua lượt bằng KNB ({number}/{count})."
                        ):
                            return
                    extras = []
                    if task == "Đóng góp KNB":
                        extras.append(f"lượt {number}/{count}")
                    if task == "Thăm dò lãnh địa":
                        extras.append(
                            "có mua lượt bằng KNB" if self._config.get("tham_do_lanh_dia_knb")
                            else "chỉ dùng lượt miễn phí"
                        )
                    suffix = f" ({', '.join(extras)})" if extras else ""
                    if not self._mock_tick(f"{task}: chạy thử hoàn tất{suffix}."):
                        return
                    self._emit_task_progress(task, "running", number, count)
                    self._progress_completed += 1
                    self._emit_mock_progress(0, f"Hoàn thành lượt {self._progress_completed}/{total}: {task} {number}/{count}")
            self._emit_task_progress(task, "done", count, count)
        self.log_message.emit("Hoàn tất chạy thử tất cả nhiệm vụ.")

    def _run_clone_mock(self) -> None:
        """Chạy thử thứ tự tài khoản/nhiệm vụ, tuyệt đối không kết nối game."""
        accounts = load_accounts(self._config.get("clone_account_file", ""))
        task_specs = (
            ("clone_login", "Đăng nhập"),
            ("clone_receive_quoc_van", "Hoạt động -> Phúc lợi -> Nhận lễ bao quốc vận"),
            ("clone_daily_check_in", "Hoạt động -> Phúc lợi -> Điểm danh"),
            ("clone_logout", "Đăng xuất"),
        )
        selected = [
            (key, label) for key, label in task_specs
            if key != "clone_logout" and self._config.get(key)
        ]
        guild_mock_tasks = (
            ("clone_guild_check_in", "Báo danh quân đoàn"),
            ("clone_receive_lucky_bag", "Nhận túi phúc"),
            ("clone_guild_fortune", "Cầu vận quân đoàn (5 lần)"),
        )
        selected_guild = [
            (key, label) for key, label in guild_mock_tasks
            if self._config.get(key)
        ]
        if selected_guild:
            selected.extend([
                ("clone_enter_guild", "Vào màn hình Quân đoàn"),
                *selected_guild,
                ("clone_close_guild", "Thoát màn hình Quân đoàn"),
            ])
        if self._config.get("clone_logout", True):
            selected.append(("clone_logout", "Đăng xuất"))
        enabled_accounts = [account for account in accounts if account.enabled]
        total = len(enabled_accounts)
        if total == 0:
            self.log_message.emit("Tab Clone: không có tài khoản hoặc nhiệm vụ để chạy.")
            self._emit_overall_progress(0, 0, "Không có nhiệm vụ được chọn")
            return

        self._progress_total = total
        self._progress_completed = 0
        self._emit_overall_progress(0, total, "Bắt đầu chạy thử Clone")
        self.log_message.emit(
            f"Chạy thử Clone: {len(enabled_accounts)} tài khoản được bật, {len(accounts) - len(enabled_accounts)} tài khoản vô hiệu hóa, "
            f"{len(selected)} nhiệm vụ/tài khoản. Chế độ mô phỏng, không điều khiển game."
        )
        enabled_index = 0
        for account in accounts:
            if not account.enabled:
                self._emit_clone_account_status(account.display_name, "disabled")
                self.log_message.emit(f"Tài khoản {account.display_name}: đã vô hiệu hóa, bỏ qua.")
                continue
            enabled_index += 1
            account_index = enabled_index
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            self._emit_overall_progress(
                self._progress_completed, self._progress_total,
                f"Tài khoản {account_index}/{len(accounts)}: {account.display_name}",
            )
            self._emit_clone_account_status(account.display_name, "running")
            self.log_message.emit(
                f"Đang xử lý tài khoản: {account.display_name}"
            )
            for task_index, (_key, label) in enumerate(selected, start=1):
                self._emit_overall_progress(
                    self._progress_completed, self._progress_total,
                    f"{account.display_name} — {label} ({task_index}/{len(selected)})",
                )
                flow_step = {
                    "clone_receive_quoc_van": 2,
                    "clone_daily_check_in": 3,
                }.get(_key, task_index)
                flow_total = 6 if _key in (
                    "clone_receive_quoc_van", "clone_daily_check_in"
                ) else len(selected)
                if not self._mock_tick(
                    f"[{account.display_name}] {label}: chạy thử bước "
                    f"{flow_step}/{flow_total}."
                ):
                    return
                self._emit_task_progress(
                    f"{account.display_name} - {label}", "done", 1, 1
                )
            # Record the account only after its selected mock steps finish.
            self._emit_clone_account_result(account.display_name, True)
            self._progress_completed += 1
            progress_text = (
                f"Tiến trình tài khoản [{self._progress_completed}/{len(accounts)}]"
            )
            self.log_message.emit(progress_text)
            self._emit_overall_progress(
                self._progress_completed,
                self._progress_total,
                progress_text,
            )
        self.log_message.emit(
            "Hoàn tất chạy thử Clone. Đây chỉ là mô phỏng; chưa có thao tác trong game."
        )

    @staticmethod
    def _clear_focused_text(device) -> None:
        """Select and delete all text in the currently focused input field."""
        # Apply the same clearing sequence to both username and password fields.
        # Ctrl+A avoids leaving trailing characters when the old value is longer.
        device.shell("input keycombination KEYCODE_CTRL_LEFT KEYCODE_A")
        device.shell("input keyevent KEYCODE_DEL")

    @staticmethod
    def _input_text(device, value: str) -> None:
        """Send text safely through Android input; spaces use Android's %s syntax."""
        # Android's input command uses %s as the escape sequence for a space.
        value = value.replace(" ", "%s")
        device.shell(f"input text {shlex.quote(value)}")

    @staticmethod
    def _replace_focused_text(device, value: str) -> None:
        """Clear the focused field before entering a new username or password."""
        BotWorker._clear_focused_text(device)
        BotWorker._input_text(device, value)

    @staticmethod
    def _replace_password_text(device, value: str) -> None:
        """Clear password fields even when their widget ignores Ctrl+A."""
        # First try select-all. Some password widgets do not select their contents
        # with Ctrl+A, so also move to the end and send repeated Backspace events.
        BotWorker._clear_focused_text(device)
        device.shell("input keyevent KEYCODE_MOVE_END")
        device.shell("input keyevent " + " ".join(["KEYCODE_DEL"] * 64))
        BotWorker._input_text(device, value)

    def _run_clone_login(self, device) -> None:
        """Run the optimized Clone flow for the configured accounts."""
        from dctq_auto.tasks.clone.flow import run_clone_flow_optimize

        run_clone_flow_optimize(self, device)


    def run(self) -> None:
        try:
            self._run_impl()
        except Exception as exc:
            self._progress_failed = True
            self.log_message.emit(f"Lỗi worker: {exc}")
        finally:
            if self._progress_root_id is not None:
                descendants = self.progress_manager.get_all()
                has_failed = any(
                    item.status == ProgressStatus.FAILED
                    for item in descendants
                )
                status = (
                    ProgressStatus.STOPPED
                    if self.isInterruptionRequested()
                    else ProgressStatus.FAILED
                    if self._progress_failed or has_failed
                    else ProgressStatus.SUCCESS
                )
                message = {
                    ProgressStatus.STOPPED: "Đã dừng",
                    ProgressStatus.FAILED: "Có tác vụ thất bại",
                    ProgressStatus.SUCCESS: "Hoàn tất",
                }[status]
                self._set_root_status(status, message)

    def _run_impl(self) -> None:
        if self._mock_mode:
            self._emit_overall_progress(0, 1, "Đang chuẩn bị chạy thử")
            self.log_message.emit("Bắt đầu với cấu hình đã chọn.")
            try:
                self._run_mock()
            except Exception as exc:
                self._progress_failed = True
                self.log_message.emit(f"Lỗi chạy thử: {exc}")
            return

        self._emit_overall_progress(0, 2, "Đang kết nối ADB")
        self.log_message.emit(f"Bắt đầu với cấu hình: {self._config}")
        if not self._wait_if_paused():
            self.log_message.emit("Đã yêu cầu dừng trước khi kết nối ADB.")
            return

        try:
            client = AdbClient(serial=self._serial)
            device = client.connect()
            self.log_message.emit(f"Đã kết nối ADB: {self._serial}")
            if self._config.get("state_war_mode"):
                from dctq_auto.config.constants import _STEP_CHIEN_TRANH_QUOC_CHIEN
                from dctq_auto.tasks.common.state_war.task_state_war import (
                    run_state_war,
                )
                account = SimpleNamespace(username="Quốc chiến", display_name="Quốc chiến")
                steps = [_STEP_CHIEN_TRANH_QUOC_CHIEN]
                run_state_war(
                    self,
                    account,
                    steps,
                    device,
                    self._config.get("state_war_strategy_path", ""),
                    self.log_message.emit,
                )
                return
            if self._config.get("strategy_mode"):
                from dctq_auto.config.step_registry import get_clone_step_registry
                from dctq_auto.tasks.common.war import task_war

                account = SimpleNamespace(username="Mưu Binh", display_name="Mưu Binh")
                steps = get_clone_step_registry().get_enabled_steps(self._config)
                self._emit_overall_progress(0, 100, "Bắt đầu quy trình Chiến Tranh — Mưu Binh")
                task_war.run(
                    self,
                    account,
                    steps,
                    device,
                    None,
                    self.log_message.emit,
                )
                self.log_message.emit("Mưu Binh: đã kết thúc quy trình Chiến Tranh.")
                return
            if self._config.get("clone_mode"):
                self._run_clone_login(device)
                return
            self._emit_overall_progress(1, 2, "Đã kết nối ADB")


            if not self._wait_if_paused():
                self.log_message.emit("Đã yêu cầu dừng trước khi chụp màn hình.")
                return

            screenshot = client.save_screenshot(device, self._screenshot_dir)
            self.log_message.emit(f"Đã lưu screenshot: {screenshot}")
            self._emit_overall_progress(2, 2, "Hoàn tất bước chuẩn bị")
            self.log_message.emit(
                "Chưa thực hiện nhiệm vụ trong game: logic gameplay thật chưa được triển khai."
            )
        except Exception as exc:
            self._progress_failed = True
            self.log_message.emit(f"Lỗi: {exc}")
