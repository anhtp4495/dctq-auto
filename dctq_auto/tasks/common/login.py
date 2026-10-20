"""Các thao tác và khai báo task đăng nhập dùng chung."""

import time

from dctq_auto.tasks.base import TaskSpec

SPEC = TaskSpec(
    key="clone_login",
    label="Đăng nhập",
    description="Đăng nhập vào tài khoản đang được xử lý.",
    category="clone",
)


def submit_login_form(worker, account, device, ocr_client) -> bool:
    """Điền username/password và gửi đăng nhập; False nếu có yêu cầu dừng."""
    ocr_client.tap_ocr_target("ten_dang_nhap")
    time.sleep(0.25)
    worker._replace_focused_text(device, account.username)

    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return False

    ocr_client.tap_ocr_target("mat_khau")
    time.sleep(0.25)
    worker._replace_password_text(device, account.password)

    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return False

    time.sleep(0.3)
    ocr_client.tap_ocr_target("dang_nhap")
    worker.log_message.emit(
        f"[{account.username}] Đã gửi yêu cầu đăng nhập; đang xác minh kết quả."
    )
    return True


def verify_login(worker, account, device, ocr_client) -> tuple[bool | None, str | None]:
    """Xác minh đăng nhập qua OCR và xử lý hộp thoại lỗi thường gặp."""
    verified = False
    previous_screen_text = None
    observed_error = None
    # Allow up to 20 seconds for the game/network to respond. Require two
    # consecutive non-login OCR readings to avoid counting a transient frame.
    for _attempt in range(20):
        if not worker._wait_if_paused():
            worker.log_message.emit("Đã dừng theo yêu cầu.")
            return None, observed_error
        time.sleep(1)
        try:
            result_text = worker._screen_text(device)
        except Exception as exc:
            worker.log_message.emit(
                f"[{account.username}] Lỗi đọc màn hình khi xác minh: {exc}"
            )
            break

        normalized_result = worker._normalize_screen_text(result_text)
        if "khong dung" in normalized_result:
            observed_error = "Thông tin đăng nhập không đúng"
            worker.log_message.emit(
                f"[{account.username}] OCR phát hiện thông báo 'không đúng'; "
                "đang bấm nút Đồng ý để đóng hộp thoại."
            )
            try:
                tapped = worker._tap_ocr_word(device, ("dong", "dong y", "dong y!"))
                if not tapped:
                    ocr_client.tap_ocr_target("dong_y")
                worker.log_message.emit(
                    f"[{account.username}] Đã gửi thao tác đóng hộp thoại."
                )
                time.sleep(0.5)
            except Exception as exc:
                worker.log_message.emit(
                    f"[{account.username}] Không bấm được nút Đồng ý: {exc}"
                )
            break

        if "cap nhat thong tin ca nhan" in normalized_result:
            worker.log_message.emit(
                f"[{account.username}] Phát hiện hộp thoại cập nhật thông tin cá nhân; đang đóng hộp thoại."
            )
            try:
                ocr_client.tap_ocr_target("close_cap_nhat_thong_tin_ca_nhan")
                time.sleep(1)
                previous_screen_text = None
                continue
            except Exception as exc:
                worker.log_message.emit(
                    f"[{account.username}] Không đóng được hộp thoại cập nhật thông tin cá nhân: {exc}"
                )
                break

        observed_error = worker._login_error(result_text) or observed_error
        if worker._is_login_screen(result_text):
            previous_screen_text = None
            continue
        if not result_text.strip():
            previous_screen_text = None
            continue

        if "dang nhap" not in normalized_result and not observed_error:
            if previous_screen_text is not None:
                verified = True
                break
        previous_screen_text = result_text

    return verified, observed_error
