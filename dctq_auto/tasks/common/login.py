"""Các thao tác và khai báo task đăng nhập dùng chung."""

import time
from pathlib import Path

import cv2
import numpy as np

from dctq_auto.tasks.base import TaskSpec
from dctq_auto.vision.template_matching import match_template

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
    """Xác minh kết quả đăng nhập bằng template matching, không dùng OCR.

    Chỉ template wrong_username_or_pass làm đăng nhập thất bại. Các template
    waiting, profile, update_information và trường hợp không khớp template
    nào đều được xem là không có bằng chứng sai thông tin đăng nhập.
    """
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    time.sleep(1)
    try:
        screenshot = device.screenshot()
        # PIL screenshot -> OpenCV BGR image for match_template.
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình để xác minh đăng nhập: {exc}. "
            "Tiếp tục theo quy tắc: không phát hiện template sai thông tin thì trả về thành công."
        )
        return True, None

    template_root = Path("resources/screens/accounts")
    templates = (
        ("wrong_username_or_pass", template_root / "wrong_username_or_pass.png", False),
        ("waiting", template_root / "waiting.png", True),
        ("profile", template_root / "profile.png", True),
        ("update_information", template_root / "update_information.png", True),
    )

    for template_name, template_path, is_success_state in templates:
        if not template_path.is_file():
            worker.log_message.emit(
                f"[{account.username}] Chưa có template {template_name}: {template_path}; bỏ qua template này."
            )
            continue
        try:
            match = match_template(
                screen_bgr,
                template_path,
                threshold=0.85,
                grayscale=True,
            )
        except Exception as exc:
            worker.log_message.emit(
                f"[{account.username}] Lỗi template matching {template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        worker.log_message.emit(
            f"[{account.username}] Template matching phát hiện {template_name} "
            f"(score={match.score:.3f}, rect={match.rect})."
        )
        if not is_success_state:
            reason = "Thông tin đăng nhập không đúng"
            worker.log_message.emit(
                f"[{account.username}] Đăng nhập thất bại: phát hiện template wrong_username_or_pass."
            )
            return False, reason

    worker.log_message.emit(
        f"[{account.username}] Không phát hiện template wrong_username_or_pass; xem như đăng nhập thành công."
    )
    return True, None
