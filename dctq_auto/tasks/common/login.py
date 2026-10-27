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


def verify_login(worker, account, device, ocr_client) -> tuple[bool | None, str | None]:
    """Xác minh đăng nhập bằng các template được khai báo trong templates.json.

    Chỉ phát hiện template accounts.wrong_username_or_pass mới trả về False.
    Các trạng thái còn lại, hoặc không khớp template nào, trả về True.
    Hàm này không sử dụng OCR.
    """
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    time.sleep(1)
    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình xác minh: {exc}; "
            "không có bằng chứng wrong_username_or_pass nên xem như thành công theo quy tắc hiện tại."
        )
        return True, None

    # get_templates tự đọc cấu hình, cắt ảnh và cache template đã tải.
    template_names = (
        "wrong_username_or_pass",
        "waiting",
        "profile",
        "update_information",
    )
    templates = get_templates(template_names, screen_name="accounts")

    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            continue
        threshold = template.threshold
        method = template.method

        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=threshold,
                method=method,
                grayscale=True,
            )
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
            threshold=threshold,
        )
        if template_name == "wrong_username_or_pass":
            reason = "Thông tin đăng nhập không đúng"
            worker.log_message.emit(
                f"[{account.username}] Đăng nhập thất bại: phát hiện template wrong_username_or_pass."
            )
            return False, reason

    worker.log_message.emit(
        f"[{account.username}] Không phát hiện template wrong_username_or_pass; "
        "xem như đăng nhập thành công."
    )
    return True, None
