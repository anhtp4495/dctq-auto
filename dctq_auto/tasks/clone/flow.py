"""Luồng dùng chung cho đăng nhập/đăng xuất và thao tác game theo tài khoản.

Tách khỏi GUI worker để các tab/nhiệm vụ có thể gọi lại cùng một luồng.
"""
import re
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
    total = len(accounts)
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
    for index, account in enumerate(accounts, start=1):
        if not self._wait_if_paused():
            self.log_message.emit("Đã dừng theo yêu cầu.")
            return

        self.progress_changed.emit(
            processed_count, total,
            f"Tài khoản {index}/{total}: {account.username} — Đăng nhập",
        )
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
        # "Quan chức" is the trusted profile marker; OCR can include its level
        # after it (for example, "Quan chức 4768").
        profile_found = False
        self.log_message.emit(
            f"[{account.username}] Đăng nhập có vẻ thành công; xác minh bằng cách mở mục profile."
        )
        # Tap the profile icon, then check for the "Thông tin của tôi" panel.
        try:
            ocr_client.tap_ocr_target("profile")
            time.sleep(1)
        except Exception as exc:
            self.log_message.emit(
                f"[{account.username}] Không mở được mục profile bằng tọa độ OCR: {exc}"
            )

        for profile_attempt in range(30):  # up to ~60 seconds
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if profile_attempt:
                time.sleep(2)
            try:
                profile_text = self._screen_text(device)
            except Exception as exc:
                self.log_message.emit(
                    f"[{account.username}] Lỗi OCR khi chờ profile: {exc}"
                )
                continue

            normalized_profile = self._normalize_screen_text(profile_text)
            # The opened profile panel is identified by its title, then closed
            # with the saved top-right close target so the game returns to normal.
            if "thong tin cua toi" in normalized_profile:
                try:
                    ocr_client.tap_ocr_target("close_thong_tin_cua_toi")
                    time.sleep(0.7)
                    profile_found = True
                    self.log_message.emit(
                        f"[{account.username}] Đã xác minh profile qua tiêu đề 'Thông tin của tôi' và đóng bảng profile."
                    )
                except Exception as exc:
                    self.log_message.emit(
                        f"[{account.username}] Nhận diện được profile nhưng không đóng được bảng thông tin: {exc}"
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

        if self._config.get("clone_guild_check_in"):
            # Open the guild chat/entry panel, then only enter the guild when
            # OCR confirms one of the trusted labels supplied by the user.
            self.task_progress_changed.emit(
                f"{account.username} - Báo danh quân đoàn", "running", 0, 1
            )
            try:
                self.log_message.emit(
                    f"[{account.username}] Đang mở mục Quân đoàn qua nút chat quân đoàn."
                )
                ocr_client.tap_ocr_target("button_chat_quan_doan")
                time.sleep(1.5)
                guild_entry_found = False
                last_guild_text = ""
                for guild_attempt in range(5):
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng theo yêu cầu.")
                        return
                    last_guild_text = self._normalize_screen_text(self._screen_text(device))
                    trusted_guild_labels = (
                        "quoc chien", "su do", "quoc chien do",
                        "doan truong", "doan pho", "quan su",
                        "thanh vien", "tinh anh", "toi can tang vien",
                    )
                    if any(label in last_guild_text for label in trusted_guild_labels):
                        guild_entry_found = True
                        self.log_message.emit(
                            f"[{account.username}] OCR xác nhận giao diện chat/quân đoàn: "
                            f"{last_guild_text[:220]}"
                        )
                        break
                    if guild_attempt < 4:
                        time.sleep(1)
                if not guild_entry_found:
                    # OCR can miss the trusted labels on the chat screen. The user
                    # confirmed that the game is already showing the guild chat, so
                    # cautiously try the known entry button once, then inspect again.
                    self.log_message.emit(
                        f"[{account.username}] Chưa thấy từ khóa tin cậy; thử bấm "
                        "'Vào quân đoàn' một lần và kiểm tra màn hình sau đó."
                    )
                ocr_client.tap_ocr_target("vao_quan_doan")
                time.sleep(2)
                try:
                    after_entry_text = self._normalize_screen_text(self._screen_text(device))
                except Exception as ocr_exc:
                    after_entry_text = ""
                    self.log_message.emit(
                        f"[{account.username}] Lỗi OCR sau khi bấm Vào quân đoàn: {ocr_exc}"
                    )
                guild_screen_markers = (
                    "doan truong", "doan pho", "quan su", "thanh vien",
                    "tinh anh", "toi can tang vien", "tin he thong",
                )
                if any(marker in after_entry_text for marker in guild_screen_markers):
                    self.log_message.emit(
                        f"[{account.username}] Đã xác nhận giao diện quân đoàn sau khi bấm: "
                        f"{after_entry_text[:220]}"
                    )
                else:
                    self.log_message.emit(
                        f"[{account.username}] Đã gửi thao tác Vào quân đoàn; chưa thấy "
                        f"từ khóa xác nhận rõ. OCR: {after_entry_text[:220] or '(trống)'}"
                    )
                self.log_message.emit(
                    f"[{account.username}] Đang thực hiện báo danh quân đoàn."
                )
                ocr_client.tap_ocr_target("bao_danh_nhan_thuong")
                time.sleep(1.5)
                try:
                    check_in_text = self._normalize_screen_text(self._screen_text(device))
                except Exception as ocr_exc:
                    check_in_text = ""
                    self.log_message.emit(
                        f"[{account.username}] Không đọc được OCR sau khi bấm Báo danh: {ocr_exc}"
                    )
                self.log_message.emit(
                    f"[{account.username}] Đã gửi thao tác 'Báo danh nhận thưởng'. "
                    f"OCR sau thao tác: {check_in_text[:220] or '(trống)'}"
                )
                # A tap alone does not prove that the server granted the reward.
                # Keep this task running until a reliable success marker is known.

            except Exception as exc:
                self.log_message.emit(
                    f"[{account.username}] Không mở được mục quân đoàn: {exc}"
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Báo danh quân đoàn", "failed", 0, 1
                )

        if self._config.get("clone_receive_lucky_bag"):
            try:
                self.log_message.emit(
                    f"[{account.username}] Đang kiểm tra cửa hàng quân đoàn để mở Túi phúc."
                )
                shop_text = ""
                shop_markers = (
                    "cua hang quan doan", "tui phuc", "anh hung",
                    "cau van quan doan", "lanh tui phuc",
                )
                for shop_attempt in range(3):
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng theo yêu cầu.")
                        return
                    shop_text = self._normalize_screen_text(self._screen_text(device))
                    if any(marker in shop_text for marker in shop_markers):
                        break
                    if shop_attempt < 2:
                        time.sleep(1)
                if any(marker in shop_text for marker in shop_markers):
                    self.log_message.emit(
                        f"[{account.username}] Đã nhận diện mục Túi phúc/cửa hàng quân đoàn: "
                        f"{shop_text[:220]}"
                    )
                    ocr_client.tap_ocr_target("tui_phuc")
                    time.sleep(1.5)
                    bag_text = ""
                    bag_screen_found = False
                    for bag_attempt in range(5):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu.")
                            return
                        bag_text = self._normalize_screen_text(self._screen_text(device))
                        has_count = re.search(r"\b\d+\s+30\b", bag_text) is not None
                        bag_markers = (
                            "tui phuc tuong", "tui phuc truong thanh",
                            "tui phuc knb", "co so",
                        )
                        if has_count or any(marker in bag_text for marker in bag_markers):
                            bag_screen_found = True
                            break
                        if bag_attempt < 4:
                            time.sleep(1)
                    if bag_screen_found:
                        self.log_message.emit(
                            f"[{account.username}] Đã xác nhận màn hình Túi phúc: {bag_text[:220]}"
                        )
                        for target in ("tui_phuc_thuong", "tui_phuc_truong_thanh", "tui_phuc_knb"):
                            if not self._wait_if_paused():
                                self.log_message.emit("Đã dừng theo yêu cầu.")
                                return
                            ocr_client.tap_ocr_target(target)
                            time.sleep(1)
                        ocr_client.tap_ocr_target("close_tui_phuc")
                        time.sleep(0.8)
                        self.log_message.emit(
                            f"[{account.username}] Đã bấm lần lượt 3 mục Túi phúc và đóng cửa sổ."
                        )
                    else:
                        self.log_message.emit(
                            f"[{account.username}] Đã bấm Túi phúc nhưng OCR chưa xác nhận "
                            f"đúng màn hình; không bấm các vị trí nhận. OCR: {bag_text[:220] or '(trống)'}"
                        )
                else:
                    self.log_message.emit(
                        f"[{account.username}] Chưa nhận diện được cửa hàng/Túi phúc; bỏ qua để tránh bấm nhầm. "
                        f"OCR: {shop_text[:220] or '(trống)'}"
                    )
            except Exception as exc:
                self.log_message.emit(
                    f"[{account.username}] Lỗi thao tác nhận Túi phúc: {exc}"
                )
                self.task_progress_changed.emit(
                    f"{account.username} - Nhận Túi phúc", "failed", 0, 1
                )

        if self._config.get("clone_guild_fortune"):
            from dctq_auto.tasks.common.guild_logistics import run_guild_logistics

            if not run_guild_logistics(self, account, device, ocr_client):
                return

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

