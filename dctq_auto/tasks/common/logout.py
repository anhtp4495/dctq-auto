"""Quy trình và khai báo task đăng xuất dùng chung."""

import time

import cv2
import numpy as np

from dctq_auto.tasks.base import TaskSpec
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_report import report_template_match

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


def run_logout_flow(worker, account, device, ocr_client) -> bool | None:
    """Nhận diện trạng thái hiện tại và đệ quy xử lý đến màn hình đăng nhập."""
    if not worker._config.get("clone_logout", True):
        return True

    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None

    template_names = (
        "accounts/login_form",
        "accounts/waiting",
        "accounts/profile",
        "accounts/account_settings_action",
        "accounts/account_settings_change",
        "accounts/account_settings_confirm",
    )

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình khi đăng xuất: {exc}"
        )
        return False

    templates = get_templates(template_names)
    detected_state = None

    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            continue

        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=template.threshold,
                method=template.method,
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
            context=f"[{account.username}] Đăng xuất:",
            template_name=template_name.rsplit("/", 1)[-1],
            display_name=template.display_name,
            match=match,
            threshold=template.threshold,
        )
        detected_state = template_name.rsplit("/", 1)[-1]
        detected_match = match
        break

    if detected_state == "login_form":
        worker.log_message.emit(
            f"[{account.username}] Đã về màn hình đăng nhập sau khi đổi tài khoản."
        )
        return True

    if detected_state == "waiting":
        worker.log_message.emit(
            f"[{account.username}] Đang ở màn hình chờ; kiểm tra lại sau 3 giây."
        )
        time.sleep(3)
        return run_logout_flow(worker, account, device, ocr_client)

    if detected_state == "profile":
        tap_x = int(screenshot.width * 0.029167)
        tap_y = int(screenshot.height * 0.071296)
        worker.log_message.emit(
            f"[{account.username}] Mở profile tại ({tap_x}, {tap_y}); "
            "sẽ nhận diện lại màn hình sau thao tác."
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(1.5)
        return run_logout_flow(worker, account, device, ocr_client)

    if detected_state in (
        "account_settings_action",
        "account_settings_change",
        "account_settings_confirm",
    ):
        tap_x = (detected_match.left + detected_match.right) // 2
        tap_y = (detected_match.top + detected_match.bottom) // 2
        worker.log_message.emit(
            f"[{account.username}] Bấm giữa template {detected_state} tại ({tap_x}, {tap_y})."
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(1)
        return run_logout_flow(worker, account, device, ocr_client)

    worker.log_message.emit(
        f"[{account.username}] Không nhận diện được trạng thái đăng xuất."
    )
    return False

def handle_post_logout(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Xác minh trạng thái sau khi đăng xuất bằng template matching."""
    if not worker._config.get("clone_logout", True):
        worker.log_message.emit(
            f"[{account.username}] Bỏ qua đăng xuất theo cấu hình."
        )
        return True, None

    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    template_names = (
        "accounts/login_form",
        "accounts/waiting",
    )

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình để xác minh đăng xuất: {exc}"
        )
        return False, None

    templates = get_templates(template_names)

    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            continue

        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=template.threshold,
                method=template.method,
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
            context=f"[{account.username}] Xác minh đăng xuất:",
            template_name=template_name.rsplit("/", 1)[-1],
            display_name=template.display_name,
            match=match,
            threshold=template.threshold,
        )

        state = template_name.rsplit("/", 1)[-1]
        if state == "login_form":
            worker.log_message.emit(
                f"[{account.username}] Đăng xuất thành công."
            )
            return True, None

        if state == "waiting":
            worker.log_message.emit(
                f"[{account.username}] Đang chờ đăng xuất; kiểm tra lại sau 3 giây."
            )
            time.sleep(3)
            return handle_post_logout(worker, account, device, ocr_client)

    worker.log_message.emit(
        f"[{account.username}] Xác minh đăng xuất thất bại."
    )
    return False, "Không xác minh được trạng thái đăng xuất."


def logout_account(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Điều phối toàn bộ quy trình đăng xuất tài khoản."""
    prepared, error = prepare_logout(worker, account, device, ocr_client)
    if prepared is not True:
        return prepared, error or ("Đã dừng theo yêu cầu" if prepared is None else "Không thể chuẩn bị đăng xuất")

    logout_result = run_logout_flow(worker, account, device, ocr_client)
    if logout_result is not True:
        if logout_result is None:
            return None, None
        return False, "Không thể thực hiện thao tác đăng xuất"

    return handle_post_logout(worker, account, device, ocr_client)

