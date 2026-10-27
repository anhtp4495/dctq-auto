"""Luồng dùng chung cho đăng nhập/đăng xuất và thao tác game theo tài khoản.

Tách khỏi GUI worker để các tab/nhiệm vụ có thể gọi lại cùng một luồng.
"""
import re
from difflib import SequenceMatcher
import shlex
import time
import unicodedata
from pathlib import Path

import pytesseract
from PIL import ImageOps

from dctq_auto.adb.client import AdbClient
from dctq_auto.automation.battle_testkit import BattleSnapshot, run_mock_battle
from dctq_auto.tasks.common.accounts import load_accounts


def run_clone_flow(self, device) -> None:
    """Log in clone accounts using the confirmed login-screen OCR coordinates."""
    accounts = load_accounts(self._config.get("clone_account_file", ""))
    enabled_accounts = [account for account in accounts if account.enabled]
    total = len(enabled_accounts)
    for account in accounts:
        if not account.enabled:
            self.clone_account_status.emit(account.username, "disabled")
            self.log_message.emit(f"Tài khoản {account.username}: đã vô hiệu hóa, bỏ qua.")
    if total == 0:
        self.log_message.emit("Clone: tất cả tài khoản đều đã vô hiệu hóa; không có tài khoản để chạy.")
        self.progress_changed.emit(0, 0, "Không có tài khoản được bật")
        return
    if not self._config.get("clone_login", True):
        self.log_message.emit(
            "Clone: chưa chọn Đăng nhập; các thao tác Clone khác chưa được triển khai."
        )
        self.progress_changed.emit(0, total, f"0/{total} tài khoản thành công")
        return

    # Use saved OCR boxes so taps follow the source screenshot resolution.
    # These normalized names match the three OCR results supplied by the user.
    ocr_client = AdbClient(serial=self._serial)

    success_count = 0
    failed_count = 0
    processed_count = 0
    account_results: list[tuple[str, str]] = []

    def emit_account_progress(_status: str = "") -> None:
        self.progress_changed.emit(
            processed_count,
            total,
            f"{success_count} thành công | {failed_count} thất bại",
        )

    emit_account_progress("Bắt đầu")
    index = 0
    for account in accounts:
        if not account.enabled:
            continue
        index += 1
        # Per-account flag: the next clone may have a newly opened guild screen.
        self._config["_clone_guild_screen_closed"] = False
        if not self._wait_if_paused():
            self.log_message.emit("Đã dừng theo yêu cầu.")
            return

        self.progress_changed.emit(
            processed_count, total,
            f"Tài khoản {index}/{total}: {account.username} — Đăng nhập",
        )
        self.clone_account_status.emit(account.username, "running")
        self.log_message.emit(
            f"[{account.username}] Kiểm tra màn hình đăng nhập ({index}/{total})."
        )
        try:
            screen_text = self._screen_text(device)
        except Exception as exc:
            failed_count += 1
            processed_count += 1
            account_results.append((account.username, f"FAILED — lỗi OCR: {exc}"))
            self.clone_account_result.emit(account.username, False)
            self.log_message.emit(
                f"[{account.username}] FAILED — không đọc được màn hình bằng OCR: {exc}. "
                "Bỏ qua account này và thử account tiếp theo."
            )
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "failed", 0, 1
            )
            emit_account_progress(f"FAILED: {account.username}")
            continue

        if not self._is_login_screen(screen_text):
            normalized_screen = self._normalize_screen_text(screen_text)
            self.log_message.emit(
                f"[{account.username}] OCR màn hình hiện tại: "
                f"{normalized_screen[:240] or '(không đọc được chữ)'}"
            )
            failed_count += 1
            processed_count += 1
            account_results.append((account.username, "FAILED — không nhận diện được màn hình đăng nhập"))
            self.clone_account_result.emit(account.username, False)
            self.log_message.emit(
                f"[{account.username}] FAILED — không nhận diện được màn hình đăng nhập; "
                "bỏ qua account này. Không nhập thông tin vào màn hình chưa xác định."
            )
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "failed", 0, 1
            )
            emit_account_progress(f"FAILED: {account.username}")
            # If an earlier account is still logged in, we cannot safely switch users
            # until logout is implemented. Otherwise try the next account.
            if success_count:
                self.log_message.emit(
                    "Không thể tiếp tục đăng nhập account kế tiếp vì chưa có luồng đăng xuất an toàn."
                )
                break
            continue

        try:
            from dctq_auto.tasks.common.login import submit_login_form

            if not submit_login_form(self, account, device, ocr_client):
                return
        except Exception as exc:
            failed_count += 1
            processed_count += 1
            account_results.append((account.username, f"FAILED — lỗi thao tác đăng nhập: {exc}"))
            self.clone_account_result.emit(account.username, False)
            self.log_message.emit(
                f"[{account.username}] FAILED — không thể nhập thông tin hoặc bấm đăng nhập: "
                f"{exc}. Bỏ qua account này và thử account tiếp theo."
            )
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "failed", 0, 1
            )
            emit_account_progress(f"FAILED: {account.username}")
            continue

        from dctq_auto.tasks.common.login import verify_login

        verified, observed_error = verify_login(self, account, device, ocr_client)
        if verified is None:
            return

        if not verified:
            failed_count += 1
            processed_count += 1
            if observed_error:
                reason = observed_error
            else:
                reason = "không xác nhận được đăng nhập thành công sau 20 giây"
            account_results.append((account.username, f"FAILED — {reason}"))
            self.clone_account_result.emit(account.username, False)
            self.log_message.emit(
                f"[{account.username}] FAILED — {reason}. "
                "Bỏ qua account này và chuyển sang account tiếp theo."
            )
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "failed", 0, 1
            )
            emit_account_progress(f"FAILED: {account.username}")
            continue

        # The game may need extra time to finish loading the profile.
        # Read only the top panel area and use a 75% fuzzy match for its title.
        profile_found = False
        self.log_message.emit(
            f"[{account.username}] Đăng nhập có vẻ thành công; xác minh bằng cách mở mục profile."
        )
        try:
            ocr_client.tap_ocr_target("profile")
            time.sleep(1)
        except Exception as exc:
            self.log_message.emit(
                f"[{account.username}] Không mở được mục profile bằng tọa độ OCR: {exc}"
            )

        # Rect lấy từ ảnh OCR debug ở độ phân giải chuẩn 1920x1080.
        profile_header_rect = (519, 41, 1394, 200)
        title_target = "thong tin cua toi"

        def title_match_75(text: str) -> bool:
            normalized = self._normalize_screen_text(text)
            normalized = re.sub(r"[^a-z0-9 ]", " ", normalized)
            normalized = " ".join(normalized.split())
            target = " ".join(title_target.split())
            if target in normalized:
                return True
            # Compare normalized OCR text against the expected title.
            return SequenceMatcher(None, normalized, target).ratio() >= 0.75

        for profile_attempt in range(30):  # up to ~60 seconds
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if profile_attempt:
                time.sleep(2)
            try:
                image = device.screenshot()
                scale_x, scale_y = image.width / 1920, image.height / 1080
                scaled_rect = (
                    round(profile_header_rect[0] * scale_x),
                    round(profile_header_rect[1] * scale_y),
                    round(profile_header_rect[2] * scale_x),
                    round(profile_header_rect[3] * scale_y),
                )
                profile_text = self._screen_text_in_rect(device, scaled_rect)
            except Exception as exc:
                self.log_message.emit(
                    f"[{account.username}] Lỗi OCR khi chờ tiêu đề profile: {exc}"
                )
                continue

            normalized_profile = self._normalize_screen_text(profile_text)
            # If the tap-kich notice overlaps the profile header area, close it first.
            if "dich quan tap kich" in normalized_profile or "dich_quan_tap_kich" in normalized_profile:
                try:
                    ocr_client.tap_ocr_target("close_dich_quan_tap_kich")
                    time.sleep(0.8)
                    self.log_message.emit(
                        f"[{account.username}] OCR vùng profile phát hiện 'dich_quan_tap_kich'; "
                        "đã bấm đóng thông báo trước khi xử lý profile."
                    )
                    # Re-read the same small area after closing the notice.
                    profile_text = self._screen_text_in_rect(device, scaled_rect)
                    normalized_profile = self._normalize_screen_text(profile_text)
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Không đóng được thông báo 'dich_quan_tap_kich': {exc}"
                    )
                    continue

            if title_match_75(normalized_profile):
                try:
                    ocr_client.tap_ocr_target("close_thong_tin_cua_toi")
                    time.sleep(0.7)
                    profile_found = True
                    self.log_message.emit(
                        f"[{account.username}] Đã xác minh profile qua tiêu đề 'Thông tin của tôi' "
                        "khớp OCR từ 75% trở lên và đóng bảng profile."
                    )
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Nhận diện được tiêu đề profile nhưng không đóng được bảng thông tin: {exc}"
                    )
                break

        if not profile_found:
            failed_count += 1
            processed_count += 1
            account_results.append((account.username, "FAILED — không thấy profile quan_chuc sau 60 giây"))
            self.clone_account_result.emit(account.username, False)
            self.log_message.emit(
                f"[{account.username}] FAILED — không thấy profile 'quan_chuc' sau 60 giây; "
                "bỏ qua account này và thử account tiếp theo."
            )
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "failed", 0, 1
            )
            emit_account_progress(f"FAILED: {account.username}")
            # Profile may be logged in but not recognized. Avoid entering another
            # account on an unknown screen unless a safe logout flow exists.
            if index < total:
                self.log_message.emit(
                    "Tạm dừng chuyển account vì chưa xác nhận được màn hình đăng nhập sau lỗi profile."
                )
                break
            continue

        # Dùng đúng flow đã được kiểm chứng ở tab Tác vụ; không nhầm checkbox này
        # với Điểm danh hằng ngày.
        if self._config.get("clone_receive_quoc_van"):
            task_label = f"{account.username} - Nhận lễ bao quốc vận"
            self.task_progress_changed.emit(task_label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu trước khi nhận lễ bao Quốc vận.")
                return
            self.log_message.emit(
                f"[{account.username}] Bắt đầu nhận lễ bao Quốc vận."
            )
            try:
                receive_quoc_van_ok = self._run_receive_quoc_van(device, ocr_client)
            except Exception as exc:
                receive_quoc_van_ok = False
                self.log_message.emit(
                    f"[{account.username}] Lỗi khi nhận lễ bao Quốc vận: {exc}"
                )
            if receive_quoc_van_ok:
                self.task_progress_changed.emit(task_label, "done", 1, 1)
                self.log_message.emit(
                    f"[{account.username}] Đã chạy xong luồng nhận lễ bao Quốc vận."
                )
            else:
                self.task_progress_changed.emit(task_label, "failed", 0, 1)
                self.log_message.emit(
                    f"[{account.username}] Nhận lễ bao Quốc vận thất bại; "
                    "tiếp tục các tác vụ Clone khác."
                )

        if self._config.get("clone_daily_check_in"):
            task_label = f"{account.username} - Điểm danh"
            self.task_progress_changed.emit(task_label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            self.log_message.emit(
                f"[{account.username}] Bắt đầu điểm danh hằng ngày."
            )
            try:
                check_in_ok = self._run_daily_checkin(device, ocr_client)
            except Exception as exc:
                check_in_ok = False
                self.log_message.emit(
                    f"[{account.username}] Lỗi khi chạy điểm danh hằng ngày: {exc}"
                )
            if check_in_ok:
                self.task_progress_changed.emit(task_label, "done", 1, 1)
                self.log_message.emit(
                    f"[{account.username}] Đã chạy xong luồng điểm danh hằng ngày."
                )
            else:
                self.task_progress_changed.emit(task_label, "failed", 0, 1)
                self.log_message.emit(
                    f"[{account.username}] Điểm danh hằng ngày thất bại; tiếp tục các tác vụ Clone khác."
                )

        # Quân đoàn là một nhóm luồng chung: chỉ mở/đóng màn hình khi
        # ít nhất một trong ba tác vụ con được chọn.
        guild_tasks = (
            ("clone_guild_check_in", "bao_danh_quan_doan", "Báo danh quân đoàn"),
            ("clone_receive_lucky_bag", "task_receive_lucky_bag", "Nhận túi phúc"),
            ("clone_guild_fortune", "task_guild_fortune", "Cầu vận quân đoàn (5 lần)"),
        )
        selected_guild_tasks = [
            (config_key, task_key, label)
            for config_key, task_key, label in guild_tasks
            if self._config.get(config_key)
        ]
        guild_screen_opened = False
        if selected_guild_tasks:
            enter_label = f"{account.username} - Vào màn hình Quân đoàn"
            self.task_progress_changed.emit(enter_label, "running", 0, 1)
            self.log_message.emit(
                f"[{account.username}] Có chọn {len(selected_guild_tasks)} tác vụ Quân đoàn; "
                "bắt đầu flow Vào Quân đoàn dùng chung với tab Tác vụ."
            )
            guild_screen_opened = self._run_enter_guild(device, ocr_client)
            self.task_progress_changed.emit(
                enter_label, "done" if guild_screen_opened else "failed",
                1 if guild_screen_opened else 0, 1,
            )

            if guild_screen_opened:
                for config_key, task_key, label in selected_guild_tasks:
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng theo yêu cầu trong nhóm tác vụ Quân đoàn.")
                        return
                    self.log_message.emit(
                        f"[{account.username}] Bắt đầu tác vụ Quân đoàn: {label}."
                    )
                    task_ok = self._run_guild_screen_task(task_key, device, ocr_client)
                    if not task_ok:
                        self.log_message.emit(
                            f"[{account.username}] {label} thất bại; tiếp tục tác vụ Quân đoàn kế tiếp."
                        )

                # Close only after a successful, OCR-confirmed entry. Reuse the
                # saved targets used by the standalone Tác vụ tab.
                close_label = f"{account.username} - Thoát màn hình Quân đoàn"
                self.task_progress_changed.emit(close_label, "running", 0, 1)
                try:
                    self.log_message.emit(
                        f"[{account.username}] Thoát Quân đoàn — đóng màn hình bằng "
                        "close_quan_doan từ regions.json."
                    )
                    ocr_client.tap_ocr_target("close_quan_doan")
                    time.sleep(0.8)
                    image = device.screenshot()
                    scale_x, scale_y = image.width / 1920, image.height / 1080
                    rect = (
                        round(1270 * scale_x), round(968 * scale_y),
                        round(1532 * scale_x), round(1026 * scale_y),
                    )
                    after_close_text = self._normalize_screen_text(
                        self._screen_text_in_rect(device, rect)
                    )
                    if "vao quan doan" in after_close_text:
                        x, y = ocr_client.tap_ocr_target("thoat_chat_quan_doan")
                        time.sleep(0.8)
                        self.log_message.emit(
                            f"[{account.username}] OCR thấy 'vao_quan_doan'; "
                            f"đã đóng chat tại ({x}, {y})."
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Đã đóng màn hình Quân đoàn; "
                            "OCR không thấy 'vao_quan_doan' nên không bấm đóng chat. "
                            f"OCR: {after_close_text[:180] or '(trống)'}"
                        )
                    self._config["_clone_guild_screen_closed"] = True
                    self.task_progress_changed.emit(close_label, "done", 1, 1)
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Thoát màn hình Quân đoàn thất bại: {exc}"
                    )
                    self.task_progress_changed.emit(close_label, "failed", 0, 1)
            else:
                self.log_message.emit(
                    f"[{account.username}] Không xác nhận được màn hình Quân đoàn; "
                    "bỏ qua các thao tác con để tránh click nhầm."
                )
                for _config_key, _task_key, label in selected_guild_tasks:
                    self.task_progress_changed.emit(
                        f"{account.username} - {label}", "failed", 0, 1
                    )

        if self._config.get("clone_quoc_chien"):
            try:
                self.log_message.emit(
                    f"[{account.username}] Đang mở mục Chiến tranh để tìm Quốc chiến."
                )
                ocr_client.tap_ocr_target("chien_tranh")
                time.sleep(1.5)
                found_quoc_chien = False
                for attempt in range(4):
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng theo yêu cầu.")
                        return
                    screen = self._normalize_screen_text(self._screen_text(device))
                    if "quoc chien" in screen or "quoc_chien" in screen:
                        found_quoc_chien = True
                        break
                    self.log_message.emit(
                        f"[{account.username}] Chưa thấy Quốc chiến; kéo màn hình lần {attempt + 1}/3."
                    )
                    # Drag from A to B using the supplied 1920x1080 normalized points.
                    device.shell("input swipe 524 582 1574 564 500")
                    time.sleep(1.2)
                if found_quoc_chien:
                    self.log_message.emit(
                        f"[{account.username}] Đã tìm thấy mục Quốc chiến qua OCR."
                    )
                else:
                    self.log_message.emit(
                        f"[{account.username}] Không tìm thấy mục Quốc chiến sau khi kéo."
                    )
            except Exception as exc:
                self.log_message.emit(
                    f"[{account.username}] Không thể mở/tìm Quốc chiến: {exc}"
                )
                break

        # Nhận thưởng - Quân Đoàn chạy cuối cùng, sau Quốc chiến, dùng lại flow đã có ở Tab Tác vụ.
        if self._config.get("clone_reward_guild"):
            task_label = f"{account.username} - Nhận Thưởng - Quân Đoàn"
            self.task_progress_changed.emit(task_label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi nhận Thưởng - Quân Đoàn.")
                return
            self.log_message.emit(
                f"[{account.username}] Bắt đầu Nhận Thưởng - Quân Đoàn "
                "bằng luồng đã triển khai ở Tab Tác vụ."
            )
            previous_reward_flag = self._config.get("reward_weekly_doan_chien", False)
            previous_reward_label = self._config.get("_clone_reward_guild_label")
            try:
                from dctq_auto.tasks.reward_weekly_doan_chien import run_reward_weekly_doan_chien
                self._config["reward_weekly_doan_chien"] = True
                # Reuse the existing task's own progress reporting, with the Clone label.
                self._config["_clone_reward_guild_label"] = task_label
                reward_result = run_reward_weekly_doan_chien(self, device, 0, 1)
                if reward_result is None:
                    self.task_progress_changed.emit(task_label, "failed", 0, 1)
                    self.log_message.emit(
                        f"[{account.username}] Luồng Nhận Thưởng - Quân Đoàn đã dừng hoặc chưa hoàn tất."
                    )
                else:
                    self.log_message.emit(
                        f"[{account.username}] Đã kết thúc luồng Nhận Thưởng - Quân Đoàn; "
                        "xem trạng thái OCR của tác vụ để biết thành công hay thất bại."
                    )
            except Exception as exc:
                self.task_progress_changed.emit(task_label, "failed", 0, 1)
                self.log_message.emit(
                    f"[{account.username}] Nhận Thưởng - Quân Đoàn thất bại: {exc}"
                )
            finally:
                self._config["reward_weekly_doan_chien"] = previous_reward_flag
                if previous_reward_label is None:
                    self._config.pop("_clone_reward_guild_label", None)
                else:
                    self._config["_clone_reward_guild_label"] = previous_reward_label

        # Close the guild panel after all selected guild-related actions,
        # then log out so the next account starts from the login screen.
        from dctq_auto.tasks.common.logout import run_logout_flow

        logout_ok = run_logout_flow(self, account, device, ocr_client)
        if logout_ok is None:
            return

        if not logout_ok:
            failed_count += 1
            processed_count += 1
            account_results.append((account.username, "FAILED — đăng xuất không xác nhận được"))
            self.clone_account_result.emit(account.username, False)
            emit_account_progress(f"FAILED: {account.username}")
            self.task_progress_changed.emit(
                f"{account.username} - Đăng nhập", "failed", 0, 1
            )
            self.log_message.emit(
                f"[{account.username}] Dừng vòng lặp Clone để tránh đăng nhập account kế tiếp "
                "khi game chưa về màn hình đăng nhập."
            )
            break

        success_count += 1
        processed_count += 1
        account_results.append((account.username, "SUCCESS"))
        self.clone_account_result.emit(account.username, True)
        self.log_message.emit(
            f"[{account.username}] SUCCESS — đăng nhập thành công, profile đã tải "
            f"({success_count} thành công, {failed_count} thất bại)."
        )
        emit_account_progress(f"SUCCESS: {account.username}")
        self.task_progress_changed.emit(
            f"{account.username} - Đăng nhập", "done", 1, 1
        )

    self.log_message.emit(
        f"Kết quả Clone: {success_count} thành công, {failed_count} thất bại, "
        f"{max(0, total - processed_count)} chưa xử lý / tổng {total} tài khoản."
    )
    if account_results:
        self.log_message.emit("TỔNG KẾT TỪNG ACCOUNT:")
        for username, result in account_results:
            self.log_message.emit(f"  {username}: {result}")
    processed_names = {username for username, _result in account_results}
    for account in accounts:
        if account.username not in processed_names:
            self.log_message.emit(f"  {account.username}: NOT PROCESSED — chưa chạy")
    if self._config.get("clone_daily_check_in"):
        self.log_message.emit(
            "Lưu ý: điểm danh hằng ngày hiện chưa có thao tác gameplay hoàn chỉnh."
        )
    if self._config.get("clone_guild_check_in"):
        self.log_message.emit(
            "Lưu ý: đã thêm thao tác bấm Báo danh quân đoàn; chưa xác minh được trạng thái nhận thưởng thành công."
        )

