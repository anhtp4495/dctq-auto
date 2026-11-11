"""Quy trình và khai báo task đăng xuất dùng chung."""

import time

import cv2
import numpy as np

from dctq_auto.tasks.base import TaskSpec
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.config.button_positions import ButtonPositions

SPEC = TaskSpec(
    key="clone_logout",
    label="Đăng xuất",
    description="Đăng xuất sau khi hoàn tất các nhiệm vụ của tài khoản.",
    category="clone",
)

def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.display_name}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def prepare_logout(worker, account, device, ocr_client) -> tuple[bool | None, str | None]:
    """Chuẩn bị trước khi đăng xuất, đóng màn hình quân đoàn nếu cần."""
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    worker.log_message.emit(
        f"[{account.display_name}] Chuẩn bị đăng xuất."
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
        "accounts3/dang_nhap",
        "accounts1/waiting",
        "accounts6/tuy_chon",
        "accounts7/cai_dat_nguoi_dung",
        "accounts8/doi_tai_khoan",
        "accounts2/man_hinh_chinh",
        "accounts5/trang_ca_nhan_tuy_chon",
    )

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.display_name}] Không chụp được màn hình khi đăng xuất: {exc}"
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
                f"[{account.display_name}] Lỗi template matching {template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        report_template_match(
            worker.log_message.emit,
            context=f"[{account.display_name}] Đăng xuất:",
            template=template,
            match=match,
        )
        detected_state = template.id
        detected_match = match
        break

    if detected_state == "dang_nhap":
        worker.log_message.emit(
            f"[{account.display_name}] Đã về màn hình đăng nhập sau khi đổi tài khoản."
        )
        return True

    if detected_state == "waiting":
        worker.log_message.emit(
            f"[{account.display_name}] Đang ở màn hình chờ; kiểm tra lại sau 3 giây."
        )
        time.sleep(3)
        return run_logout_flow(worker, account, device, ocr_client)

    if detected_state == "man_hinh_chinh":
        tap_x, tap_y = ButtonPositions().get("main", "profile")
        worker.log_message.emit(
            f"[{account.display_name}] Mở profile tại ({tap_x}, {tap_y}); "
            "sẽ nhận diện lại màn hình sau thao tác."
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(1.5)
        return run_logout_flow(worker, account, device, ocr_client)

    if detected_state == "trang_ca_nhan_tuy_chon":
        _tap_match_center(device, match, account, worker.log_message.emit)

        time.sleep(1.5)
        return run_logout_flow(worker, account, device, ocr_client)

    if detected_state in (
        "tuy_chon",
        "cai_dat_nguoi_dung",
        "doi_tai_khoan",
    ):
        tap_x = (detected_match.left + detected_match.right) // 2
        tap_y = (detected_match.top + detected_match.bottom) // 2
        worker.log_message.emit(
            f"[{account.display_name}] Bấm giữa template {detected_state} tại ({tap_x}, {tap_y})."
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(1)
        return run_logout_flow(worker, account, device, ocr_client)

    worker.log_message.emit(
        f"[{account.display_name}] Không nhận diện được trạng thái đăng xuất."
    )
    return False

# Số lần tối đa xác định game đã tải thành công
_MAX_TRY_DETECT_MAIN_SCREEN = 20

def handle_post_logout(
    worker, account, device, ocr_client, current_try: int = 1
) -> tuple[bool | None, str | None]:
    """Xác minh trạng thái sau khi đăng xuất bằng template matching."""
    if not worker._config.get("clone_logout", True):
        worker.log_message.emit(
            f"[{account.display_name}] Bỏ qua đăng xuất theo cấu hình."
        )
        return True, None

    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    template_names = (
        "accounts3/dang_nhap",
        "accounts1/waiting",
    )

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.display_name}] Không chụp được màn hình để xác minh đăng xuất: {exc}"
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
                f"[{account.display_name}] Lỗi template matching {template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        report_template_match(
            worker.log_message.emit,
            context=f"[{account.display_name}] Xác minh đăng xuất:",
            template=template,
            match=match,
        )

        state = template.id
        if state == "dang_nhap":
            worker.log_message.emit(
                f"[{account.display_name}] Đăng xuất thành công."
            )
            return True, None

        if state == "waiting":
            worker.log_message.emit(
                f"[{account.display_name}] Đang chờ đăng xuất; kiểm tra lại sau 3 giây."
            )
            time.sleep(3)
            return handle_post_logout(worker, account, device, ocr_client)

    if current_try < _MAX_TRY_DETECT_MAIN_SCREEN:
        worker.log_message.emit(f"[{account.display_name}] Chưa xác định đã đã đăng xuất thành công - Thử lại lần {current_try}.")
        return handle_post_logout(worker, account, device, ocr_client, current_try + 1)

    worker.log_message.emit(
        f"[{account.display_name}] Đăng xuất thất bại."
    )
    return False, "Đăng xuất thất bại."


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
        #return False, "Không thể thực hiện thao tác đăng xuất"

    return handle_post_logout(worker, account, device, ocr_client)

