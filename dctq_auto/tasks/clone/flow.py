"""Luồng dùng chung cho đăng nhập/đăng xuất và thao tác game theo tài khoản.

Tách khỏi GUI worker để các tab/nhiệm vụ có thể gọi lại cùng một luồng.
"""
import re
import cv2
import numpy as np
from difflib import SequenceMatcher
import shlex
import time
import unicodedata
from pathlib import Path

import pytesseract
from PIL import ImageOps

from dctq_auto.adb.client import AdbClient
from dctq_auto.automation.battle_testkit import BattleSnapshot, run_mock_battle
from dctq_auto.tasks.common.accounts import CURRENT_ACCOUNT, GameAccount, load_accounts
from dctq_auto.config.step_registry import get_clone_step_registry
from dctq_auto.progress import ProgressStatus


def getProcessIdOfAccount(self, account) -> str | None:
    """Return the progress node ID associated with an account."""
    return self._progress_accounts.get(account.display_name)


def _get_clone_optimize_config(self) -> dict:
    """Đọc snapshot cấu hình Clone, bao gồm trạng thái các checkbox trên GUI."""
    # _config được tạo từ CloneTab.current_config(), nên các giá trị checkbox
    # đã được chuyển thành bool trước khi worker bắt đầu chạy.
    config = dict(self._config)
    from dctq_auto.tasks.common.battle.battle_config import get_battle_config
    config["battle_config"] = get_battle_config(config)

    checkbox_labels = {
        "clone_daily_check_in": "Điểm danh",
        "clone_receive_quoc_van": "Nhận lễ bao Quốc Vận",
        "clone_guild_check_in": "Báo danh quân đoàn",
        "clone_receive_lucky_bag": "Nhận túi phúc",
        "clone_guild_fortune": "Cầu vận quân đoàn",
        "clone_guild_donate_knb": "Đóng góp KNB",
        "clone_guild_donate_rations": "Đóng góp Lương Thảo",
        "clone_buy_fortune_lot": "Cửa hàng Danh Vọng - Mua quẻ lành",
        "clone_quan_su_giao_tranh": "Chiến tranh - Giao tranh",
        "clone_quan_su_tranh_ba": "Chiến tranh - Tranh Bá",
        "clone_quoc_chien": "Quốc chiến",
        "clone_reward_guild": "Nhận Thưởng - Quân Đoàn",
    }

    self.log_message.emit("Clone Optimize — Bước 1: đọc cấu hình đầu vào.")
    self.log_message.emit(
        f"Clone Optimize — File tài khoản: "
        f"{config.get('clone_account_file', '') or '(chưa chọn)'}"
    )
    for key, label in checkbox_labels.items():
        enabled = bool(config.get(key, False))
        config[key] = enabled
        self.log_message.emit(
            f"Clone Optimize — Checkbox [{label}]: {'BẬT' if enabled else 'TẮT'} ({key}={enabled})"
        )

    return config


def run_clone_flow_optimize(self, device) -> None:
    """Điều phối toàn bộ Clone Optimize: đọc config một lần rồi xử lý từng account."""
    config = _get_clone_optimize_config(self)
    # Keep the GUI snapshot (including BattleConfig) available to task runners.
    self._config.update(config)
    account_file = str(config.get("clone_account_file", "") or "").strip()
    if not account_file:
        self.log_message.emit(
            "Clone Optimize — chưa cấu hình clone_account_file; dừng ở bước đọc cấu hình."
        )
        self._emit_overall_progress(0, 0, "Chưa chọn file tài khoản Clone")
        return

    use_current_account = account_file == CURRENT_ACCOUNT
    if use_current_account:
        accounts = [GameAccount("", "", True, "Tài khoản hiện tại")]
        self.log_message.emit(
            "Clone Optimize — sử dụng phiên đăng nhập hiện tại; bỏ qua đăng nhập và đăng xuất."
        )
    else:
        try:
            accounts = load_accounts(account_file)
        except (OSError, UnicodeError, ValueError) as exc:
            self.log_message.emit(
                f"Clone Optimize — không đọc được file tài khoản {account_file!r}: {exc}"
            )
            self._emit_overall_progress(0, 0, "Không đọc được file tài khoản Clone")
            return

    enabled_accounts = [account for account in accounts if account.enabled]
    disabled_accounts = [account for account in accounts if not account.enabled]
    total = len(enabled_accounts)
    self.log_message.emit(
        f"Clone Optimize — đã nạp {len(accounts)} tài khoản: "
        f"{total} bật, {len(disabled_accounts)} vô hiệu hóa."
    )

    for account in disabled_accounts:
        self._emit_clone_account_status(account.display_name, "disabled")
        self.log_message.emit(
            f"Clone Optimize — tài khoản {account.display_name}: vô hiệu hóa, bỏ qua."
        )

    if not enabled_accounts:
        self.log_message.emit("Clone Optimize — không có tài khoản nào được bật.")
        self._emit_overall_progress(0, 0, "Không có tài khoản được bật")
        return

    step_registry = get_clone_step_registry()
    selected_steps = step_registry.get_enabled_steps(config)
    selected_steps = sorted(
        selected_steps,
        key=lambda step_id: (
            step_registry.get_priority(step_id) is None,
            step_registry.get_priority(step_id)
            if step_registry.get_priority(step_id) is not None else 0,
        ),
    )
    self.log_message.emit(
        "Clone Optimize — các bước được bật: "
        + (
            ", ".join(step_registry.get_label(step_id) for step_id in selected_steps)
            if selected_steps else "(không có)"
        )
    )

    if not selected_steps:
        self.log_message.emit("Clone Optimize — Kết thúc. Không có tác vụ nào được chọn.")
        self._emit_overall_progress(0, total, "Không có tác vụ nào được chọn")
        return

    success_count = 0
    failed_count = 0
    from dctq_auto.tasks.common.login import login_account
    from dctq_auto.tasks.common.logout import logout_account

    for index, account in enumerate(enabled_accounts, start=1):
        if not self._wait_if_paused():
            self.log_message.emit("Clone Optimize — đã dừng theo yêu cầu.")
            return

        self._emit_overall_progress(
            index - 1, total, f"Tài khoản {index}/{total}: {account.display_name}"
        )
        self._emit_clone_account_status(account.display_name, "running")
        ocr_client = AdbClient(serial=self._serial)
        if not use_current_account:
            self.log_message.emit(f"[{account.display_name}] Bắt đầu đăng nhập.")
            try:
                login_result, login_error = login_account(self, account, device, ocr_client)
            except Exception as exc:
                login_result, login_error = False, str(exc)

            if login_result is None:
                self.log_message.emit(f"[{account.display_name}] Đăng nhập bị dừng; bỏ qua tài khoản.")
                continue
            if login_result is not True:
                self.log_message.emit(
                    f"[{account.display_name}] Đăng nhập thất bại: {login_error or 'không rõ nguyên nhân'}."
                )
                self._emit_clone_account_status(account.display_name, "failed")
                self._emit_clone_account_result(account.display_name, False)
                failed_count += 1
                continue
        else:
            self.log_message.emit(f"[{account.display_name}] Bắt đầu tác vụ bằng phiên đăng nhập hiện tại.")

        # Mỗi account cần danh sách step riêng vì các task sẽ loại step đã hoàn tất.
        self._current_process_ids.clear()
        result = run_clone_flow_optimize_account(
            self, account, list(selected_steps), device, index, total
        )
        self._current_process_ids.clear()
        if result is not None:
            logout_result, logout_error = True, None
            if not use_current_account:
                try:
                    if not self._wait_if_paused():
                        self.log_message.emit(
                            f"[{account.display_name}] Đã dừng trước khi đăng xuất."
                        )
                        return
                    logout_result, logout_error = logout_account(
                        self, account, device, ocr_client
                    )
                except Exception as exc:
                    self.log_message.emit(f"[{account.display_name}] Lỗi đăng xuất: {exc}")
                    logout_result, logout_error = False, str(exc)

            if logout_result is not True:
                self.log_message.emit(
                    f"[{account.display_name}] Đăng xuất thất bại"
                    + (f": {logout_error}" if logout_error else ";")
                    + " đánh dấu tài khoản thất bại."
                )
                result = False

            self._emit_clone_account_status(
                account.display_name, "done" if result else "failed"
            )
            self._emit_clone_account_result(account.display_name, bool(result))
            if result:
                success_count += 1
            else:
                failed_count += 1
        else:
            self.log_message.emit(
                f"Clone Optimize — {account.display_name}: chưa có kết quả xử lý."
            )

    self._emit_overall_progress(
        success_count + failed_count,
        total,
        f"{success_count} thành công | {failed_count} thất bại",
    )
    self.log_message.emit(
        f"Clone Optimize — kết thúc điều phối: {success_count} thành công, "
        f"{failed_count} thất bại, {total - success_count - failed_count} chưa xử lý."
    )


def run_clone_flow_optimize_account(
    self, account, steps: list[str], device, index: int, total: int,
    _ocr_client=None, _tat_ca_thanh_cong: bool = True,
    _so_thu_tu: int = 1, _tong_steps: int | None = None,
    _common_tasks_done: bool = False,
) -> bool | None:
    """Chạy đệ quy từng bước Clone Optimize; bước đã xử lý sẽ bị xóa khỏi steps."""
    step_registry = get_clone_step_registry()
    if _tong_steps is None:
        _tong_steps = len(steps)
        # Clone Optimize chỉ hiển thị các step được chọn; ẩn node tiến trình nội bộ.
        self._clone_progress_steps_only = True
        for step_id in steps:
            self._current_process_ids[step_id] = self.UpdateOrCreateProcessProgress(
                name=step_registry.get_label(step_id),
                status="running",
                current=0,
                total=1,
                parent_id=getProcessIdOfAccount(self, account),
            )
        self.log_message.emit(
            f"[{account.display_name}] Clone Optimize — bắt đầu tác vụ tài khoản {index}/{total}."
        )
        self._config["_clone_guild_screen_closed"] = False
        _ocr_client = AdbClient(serial=self._serial)

    if not steps:
        self.log_message.emit(
            f"[{account.display_name}] Kết thúc các bước Clone Optimize: "
            f"{'thành công' if _tat_ca_thanh_cong else 'có ít nhất một bước thất bại'}."
        )
        return _tat_ca_thanh_cong

    if not self._wait_if_paused():
        self.log_message.emit(f"[{account.display_name}] Đã dừng khi đang chạy tác vụ.")
        return None

    # Chạy tuần tự các nhóm task dùng chung trước khi xử lý các nhóm khác.
    if not _common_tasks_done:
        from dctq_auto.tasks.common.activity.task_activity import run as run_activity
        from dctq_auto.tasks.common.three_kingdom.task_three_kingdom import run as run_three_kingdom
        from dctq_auto.tasks.common.guild.task_guild import run as run_guild
        from dctq_auto.tasks.common.shop.task_shop import run as run_shop
        from dctq_auto.tasks.common.war.guild.task_war_guild import run as run_war_guild

        def run_guild_war_reward(self, account, steps, device, ocr_client, log):
            """Nhận thưởng Đoàn Chiến bằng Template Matching."""
            return run_war_guild(self, account, steps, device, log)

        def run_raid_battle(self, account, steps, device, ocr_client, log):
            """Chạy Giao Tranh bằng cấu hình BattleConfig của Clone Optimize."""
            from dctq_auto.tasks.common.battle.task_battle import (
                build_clone_battle_config,
                run as run_battle,
            )

            original_config = self._config
            self._config = {
                **original_config,
                "battle_config": build_clone_battle_config(original_config),
            }
            try:
                # task_battle.run() tự cập nhật steps và trả về danh sách còn lại;
                # không còn trả về failed_tasks.
                remaining_steps = run_battle(
                    self, account, steps, device, ocr_client, log
                )
            finally:
                self._config = original_config

            return remaining_steps

        def run_ranked_battle(self, account, steps, device, ocr_client, log):
            """Chạy Tranh Bá bằng cấu hình riêng của Clone Optimize."""
            from dctq_auto.tasks.common.ranked_battle.task_ranked_battle import (
                run as run_ranked_battle_task,
            )
            from dctq_auto.tasks.common.ranked_battle.task_ranked_battle import (
                build_ranked_battle_config,
            )

            original_config = self._config
            self._config = {
                **original_config,
                "battle_config": build_ranked_battle_config(
                    original_config.get("ranked_battle_config")
                ),
            }
            try:
                remaining_steps = run_ranked_battle_task(
                    self, account, steps, device, ocr_client, log
                )
                if not getattr(self, "_ranked_battle_success", False):
                    return steps
                return remaining_steps
            finally:
                self._config = original_config

        common_tasks = (
            ("Chiến tranh - Nhận thưởng Đoàn Chiến", run_guild_war_reward, {"chien_tranh_quan_doan_nhan_thuong"}),
            ("Hoạt động", run_activity, {"hoat_dong_phuc_loi_le_bao_quoc_van", "hoat_dong_phuc_loi_diem_danh"}),
            ("Quân đoàn", run_guild, {
                "quan_doan_bao_danh", "quan_doan_tui_phuc", "quan_doan_cau_van",
                "quan_doan_dong_gop_knb", "quan_doan_dong_gop_luong_thao",
            }),
            ("Cửa hàng", run_shop, {"cua_hang_danh_vong_mua_que_lanh"}),
            ("Chiến tranh - Giao tranh", run_raid_battle, {"quan_su_giao_tranh"}),
            ("Chiến tranh - Tranh bá", run_ranked_battle, {"quan_su_tranh_ba"}),
            ("Tam Quốc Lệnh", run_three_kingdom, {"hoat_dong_nhan_thuong_tam_quoc_lenh"}),
        )
        for task_label, task_runner, group_step_ids in common_tasks:
            if not self._wait_if_paused():
                self.log_message.emit(f"[{account.display_name}] Đã dừng trước task {task_label}.")
                return None
            self.log_message.emit(
                f"[{account.display_name}] Clone Optimize — bắt đầu task {task_label}."
            )
            selected_group_steps = [
                step_id for step_id in steps if step_id in group_step_ids
            ]
            steps_before = list(steps)
            for step_id in selected_group_steps:
                self.UpdateProcessStatus(
                    process_id=self._current_process_ids[step_id],
                    status=ProgressStatus.RUNNING,
                )

            try:
                remaining_steps = task_runner(
                    self, account, steps, device, _ocr_client,
                    self.log_message.emit,
                )
                if remaining_steps is not None:
                    steps[:] = remaining_steps
                task_changed = steps != steps_before
                for step_id in selected_group_steps:
                    completed = step_id not in steps
                    self.UpdateProcessStatus(
                        process_id=self._current_process_ids[step_id],
                        status=(
                            ProgressStatus.SUCCESS
                            if completed
                            else ProgressStatus.FAILED
                        ),
                    )
                self.log_message.emit(
                    f"[{account.display_name}] Task {task_label} "
                    f"{'đã xử lý step' if task_changed else 'không có step hoàn tất'}."
                )
            except Exception as exc:
                _tat_ca_thanh_cong = False
                for step_id in selected_group_steps:
                    self.UpdateProcessStatus(
                        process_id=self._current_process_ids[step_id],
                        status=ProgressStatus.FAILED,
                    )
                self.log_message.emit(
                    f"[{account.display_name}] Task {task_label} gặp lỗi: {exc}; tiếp tục task kế tiếp."
                )

        return run_clone_flow_optimize_account(
            self,
            account,
            steps,
            device,
            index,
            total,
            _ocr_client=_ocr_client,
            _tat_ca_thanh_cong=_tat_ca_thanh_cong,
            _so_thu_tu=_so_thu_tu,
            _tong_steps=_tong_steps,
            _common_tasks_done=True,
        )

    # Các step còn lại hiện chưa có task runner riêng (ví dụ: Chiến tranh).
    # Không dùng Template Matching tổng quát ở Clone Optimize nữa.
    remaining_labels = [
        step_registry.get_label(step_id) for step_id in steps
    ]
    self.log_message.emit(
        f"[{account.display_name}] WARNING — các step chưa được triển khai task runner: "
        + ", ".join(remaining_labels)
    )
    for step_id in steps:
        self.UpdateProcessStatus(
            process_id=self._current_process_ids[step_id],
            status=ProgressStatus.FAILED,
        )
    return False

