"""Các thao tác và khai báo task đăng nhập dùng chung."""

import time

import cv2
import numpy as np

from dctq_auto.tasks.base import TaskSpec
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_report import report_template_match

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
        f"[{account.username}] Đã gửi yêu cầu đăng nhập; đang xác minh kết quả bằng template matching."
    )
    return True


def _match_account_template(screen_bgr, template):
    """So khớp một template tài khoản; trả về None nếu không khớp."""
    return match_template(
        screen_bgr,
        template.image,
        threshold=template.threshold,
        method=template.method,
        grayscale=True,
    )


def handle_post_login(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Xử lý trạng thái sau khi gửi đăng nhập bằng template matching.

    waiting: chờ 3 giây rồi kiểm tra lại bằng đệ quy.
    update_information: đóng hộp thoại rồi kiểm tra lại.
    profile: xác nhận đăng nhập thành công.
    """
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình hậu đăng nhập: {exc}"
        )
        return False, "Không xác minh được trạng thái sau đăng nhập"

    template_names = (
        "waiting",
        "update_information",
        "profile",
    )
    templates = get_templates(template_names, screen_name="accounts")

    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            continue

        try:
            match = _match_account_template(screen_bgr, template)
        except (ValueError, cv2.error) as exc:
            worker.log_message.emit(
                f"[{account.username}] Lỗi template matching {template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        report_template_match(
            worker.log_message.emit,
            context=f"[{account.username}]",
            template_name=template_name,
            display_name=template.display_name,
            match=match,
            threshold=template.threshold,
        )

        if template_name == "waiting":
            worker.log_message.emit(
                f"[{account.username}] Đang chờ đăng nhập hoàn tất; kiểm tra lại sau 3 giây."
            )
            time.sleep(3)
            return handle_post_login(worker, account, device, ocr_client)

        if template_name == "update_information":
            worker.log_message.emit(
                f"[{account.username}] Phát hiện hộp thoại cập nhật thông tin; đang đóng hộp thoại."
            )
            try:
                ocr_client.tap_ocr_target("close_cap_nhat_thong_tin_ca_nhan")
            except Exception as exc:
                worker.log_message.emit(
                    f"[{account.username}] Không đóng được hộp thoại cập nhật thông tin: {exc}"
                )
                return False, "Không đóng được hộp thoại cập nhật thông tin"
            time.sleep(1)
            return handle_post_login(worker, account, device, ocr_client)

        if template_name == "profile":
            worker.log_message.emit(f"[{account.username}] Đăng nhập thành công.")
            return True, None

    worker.log_message.emit(
        f"[{account.username}] Không nhận diện được trạng thái hậu đăng nhập từ 3 template."
    )
    return False, "Không xác định được trạng thái sau đăng nhập"


def verify_login(worker, account, device, ocr_client) -> tuple[bool | None, str | None]:
    """Xác minh thông tin đăng nhập bằng template wrong_username_or_pass."""
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    time.sleep(1)
    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình xác minh: {exc}"
        )
        return False, "Không xác minh được kết quả đăng nhập"

    templates = get_templates(
        ("wrong_username_or_pass",),
        screen_name="accounts",
    )
    template = templates.get("wrong_username_or_pass")
    if template is not None:
        try:
            match = _match_account_template(screen_bgr, template)
        except (ValueError, cv2.error) as exc:
            worker.log_message.emit(
                f"[{account.username}] Lỗi template matching wrong_username_or_pass: {exc}"
            )
            match = None

        if match is not None:
            report_template_match(
                worker.log_message.emit,
                context=f"[{account.username}]",
                template_name="wrong_username_or_pass",
                display_name=template.display_name,
                match=match,
                threshold=template.threshold,
            )
            worker.log_message.emit(
                f"[{account.username}] Đăng nhập thất bại: phát hiện template wrong_username_or_pass."
            )
            return False, "Thông tin đăng nhập không đúng"

    worker.log_message.emit(
        f"[{account.username}] Đăng nhập thành công."
    )
    return True, None


def login_account(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Điều phối toàn bộ quy trình đăng nhập tài khoản.

    Trả về (True, None) khi đã xác nhận vào game,
    (False, error) khi đăng nhập hoặc xác minh thất bại,
    và (None, None) khi worker yêu cầu dừng/tạm dừng.
    """
    if not submit_login_form(worker, account, device, ocr_client):
        return None, None

    verified, error = verify_login(worker, account, device, ocr_client)
    if verified is not True:
        return verified, error

    return handle_post_login(worker, account, device, ocr_client)
