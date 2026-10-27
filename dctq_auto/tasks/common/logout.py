"""Quy trình và khai báo task đăng xuất dùng chung."""

import time

from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_logout",
    label="Đăng xuất",
    description="Đăng xuất sau khi hoàn tất các nhiệm vụ của tài khoản.",
    category="clone",
)


def prepare_logout(worker, account, device, ocr_client) -> tuple[bool | None, str | None]:
    """Chuẩn bị trước khi đăng xuất, đóng màn hình quân đoàn nếu cần."""
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    if (
        not worker._config.get("_clone_guild_screen_closed")
        and any(
            worker._config.get(key)
            for key in (
                "clone_guild_check_in",
                "clone_receive_lucky_bag",
                "clone_guild_fortune",
            )
        )
    ):
        try:
            ocr_client.tap_ocr_target("close_quan_doan")
            time.sleep(0.8)
            worker.log_message.emit(
                f"[{account.username}] Đã gửi thao tác đóng màn hình quân đoàn."
            )
        except Exception as exc:
            worker.log_message.emit(
                f"[{account.username}] Không bấm được nút đóng quân đoàn: {exc}; "
                "vẫn tiếp tục quy trình đăng xuất."
            )

    return True, None


def _run_logout_actions(worker, account, device, ocr_client) -> bool | None:
    """Thực hiện các thao tác giao diện để chuyển tài khoản."""
    if not worker._config.get("clone_logout", True):
        return True

    try:
        if not worker._wait_if_paused():
            worker.log_message.emit("Đã dừng theo yêu cầu.")
            return None

        worker.log_message.emit(
            f"[{account.username}] Mở profile để vào Cài đặt người dùng; thử tối đa 3 lần."
        )

        profile_panel_found = False
        profile_panel_text = ""
        for profile_attempt in range(3):
            if not worker._wait_if_paused():
                worker.log_message.emit("Đã dừng theo yêu cầu.")
                return None

            screen_image = device.screenshot()
            tap_x = int(screen_image.width * 0.029167)
            tap_y = int(screen_image.height * 0.071296)
            worker.log_message.emit(
                f"[{account.username}] Bấm profile tại ({tap_x}, {tap_y}), "
                f"lần {profile_attempt + 1}/3 (ảnh {screen_image.width}x{screen_image.height})."
            )
            device.shell(f"input tap {tap_x} {tap_y}")
            time.sleep(2.5)
            profile_panel_text = worker._normalize_screen_text(worker._screen_text(device))
            if "thong tin cua toi" in profile_panel_text:
                profile_panel_found = True
                worker.log_message.emit(
                    f"[{account.username}] Đã xác minh profile qua tiêu đề "
                    f"'Thông tin của tôi' ở lần thử {profile_attempt + 1}/3."
                )
                break

            worker.log_message.emit(
                f"[{account.username}] Chưa thấy tiêu đề 'Thông tin của tôi', "
                f"thử lại {profile_attempt + 1}/3. OCR: "
                f"{profile_panel_text[:160] or '(trống)'}"
            )
            time.sleep(1.5)

        if not profile_panel_found:
            worker.log_message.emit(
                f"[{account.username}] Không xác minh được profile sau 3 lần; "
                "không chuyển sang Tùy chọn để tránh thao tác nhầm."
            )
            return False

        ocr_client.tap_ocr_target("button_tuy_chon")
        time.sleep(1.5)
        options_text = ""
        options_found = False
        for _ in range(10):
            if not worker._wait_if_paused():
                worker.log_message.emit("Đã dừng theo yêu cầu.")
                return None
            options_text = worker._normalize_screen_text(worker._screen_text(device))
            if "tuy chon" in options_text or "cai dat nguoi dung" in options_text:
                options_found = True
                break
            time.sleep(1)

        if options_found:
            worker.log_message.emit(
                f"[{account.username}] Đã xác nhận màn hình Tùy chọn: {options_text[:180]}"
            )
        else:
            worker.log_message.emit(
                f"[{account.username}] Đã xác minh profile nhưng không nhận diện được "
                f"màn hình Tùy chọn. OCR: {options_text[:180] or '(trống)'}"
            )
            return False

        ocr_client.tap_ocr_target("cai_dat_nguoi_dung")
        time.sleep(1)

        settings_text = ""
        settings_found = False
        for _ in range(10):
            if not worker._wait_if_paused():
                worker.log_message.emit("Đã dừng theo yêu cầu.")
                return None
            settings_text = worker._normalize_screen_text(worker._screen_text(device))
            if "cai dat nguoi dung" in settings_text:
                settings_found = True
                break
            time.sleep(1)

        if not settings_found:
            worker.log_message.emit(
                f"[{account.username}] Không nhận diện được giao diện Cài đặt người dùng; "
                f"không bấm Đổi tài khoản. OCR: {settings_text[:220] or '(trống)'}"
            )
            return False

        worker.log_message.emit(
            f"[{account.username}] Đã xác nhận giao diện Cài đặt người dùng."
        )
        ocr_client.tap_ocr_target("doi_tai_khoan")
        time.sleep(1.0)

        switch_confirm_text = worker._normalize_screen_text(worker._screen_text(device))
        if (
            "ban can nhap lai tai khoan mat khau" in switch_confirm_text
            or "thay doi tai khoan chu" in switch_confirm_text
        ):
            ocr_client.tap_ocr_target("button_xac_nhan")
            time.sleep(1.5)
            worker.log_message.emit(
                f"[{account.username}] Đã bấm nút xác nhận đổi tài khoản theo tọa độ lưu."
            )
        else:
            worker.log_message.emit(
                f"[{account.username}] Không nhận diện được hộp thoại xác nhận đổi tài khoản; "
                f"không bấm tọa độ xác nhận để tránh thao tác nhầm. "
                f"OCR: {switch_confirm_text[:220] or '(trống)'}"
            )
            return False

        return True
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Lỗi trong quy trình đổi tài khoản: {exc}"
        )
        return False


def handle_post_logout(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Xử lý kết quả sau khi thực hiện đăng xuất."""
    if not worker._config.get("clone_logout", True):
        worker.log_message.emit(
            f"[{account.username}] Bỏ qua đăng xuất theo cấu hình."
        )
        return True, None

    worker.log_message.emit(f"[{account.username}] Đăng xuất thành công.")
    return True, None


def logout_account(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Điều phối toàn bộ quy trình đăng xuất tài khoản."""
    prepared, error = prepare_logout(worker, account, device, ocr_client)
    if prepared is not True:
        return prepared, error or ("Đã dừng theo yêu cầu" if prepared is None else "Không thể chuẩn bị đăng xuất")

    logout_result = _run_logout_actions(worker, account, device, ocr_client)
    if logout_result is not True:
        if logout_result is None:
            return None, None
        return False, "Không thể thực hiện thao tác đăng xuất"

    return handle_post_logout(worker, account, device, ocr_client)



def run_logout_flow(worker, account, device, ocr_client) -> bool | None:
    """Tương thích với các nơi đang gọi quy trình đăng xuất dạng bool | None."""
    result, _error = logout_account(worker, account, device, ocr_client)
    return result
