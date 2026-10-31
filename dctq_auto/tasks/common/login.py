"""Các thao tác và khai báo task đăng nhập dùng chung."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
    _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
    _TEMPLATE_ACCOUNT_DANG_NHAP,
    _TEMPLATE_ACCOUNT_DICH_QUAN_TAP_KICH,
    _TEMPLATE_ACCOUNT_MAN_HINH_CHINH,
    _TEMPLATE_ACCOUNT_THONG_TIN_DANG_NHAP_KHONG_DUNG,
    _TEMPLATE_ACCOUNT_TRANG_CA_NHAN,
    _TEMPLATE_ACCOUNT_WAITING,
)
from dctq_auto.tasks.base import TaskSpec
from dctq_auto.tasks.common.logout import logout_account
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
        grayscale=template.grayscale,
    )

# Số lần tối đa xác định game đã tải thành công
_MAX_TRY_DETECT_MAIN_SCREEN = 20

def handle_post_login(
    worker, account, device, ocr_client, current_try: int = 1
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
        _TEMPLATE_ACCOUNT_DICH_QUAN_TAP_KICH,
        _TEMPLATE_ACCOUNT_WAITING,
        _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
        _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
        _TEMPLATE_ACCOUNT_MAN_HINH_CHINH,
    )
    templates = get_templates(template_names)

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
            template=template,
            match=match,
        )

        if template.id == "dich_quan_tap_kich":
            worker.log_message.emit(
                f"[{account.username}] Phát hiện Địch Quân Tập Kích; đang đóng cửa sổ."
            )
            try:
                ocr_client.tap_ocr_target("close_dich_quan_tap_kich")
            except Exception as exc:
                worker.log_message.emit(
                    f"[{account.username}] Không đóng được cửa sổ Địch Quân Tập Kích: {exc}"
                )
                return False, "Không đóng được cửa sổ Địch Quân Tập Kích"
            time.sleep(1)
            return handle_post_login(worker, account, device, ocr_client)

        if template.id == "waiting":
            worker.log_message.emit(
                f"[{account.username}] Đang chờ đăng nhập hoàn tất; kiểm tra lại sau 3 giây."
            )
            time.sleep(3)
            return handle_post_login(worker, account, device, ocr_client)

        if template.id == "cap_nhat_thong_tin" or template.id == "close_cap_nhat_thong_tin":
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

        if template.id == "man_hinh_chinh":
            worker.log_message.emit(f"[{account.username}] Đăng nhập thành công.")
            return True, None

    if current_try < _MAX_TRY_DETECT_MAIN_SCREEN:
        worker.log_message.emit(f"[{account.username}] Chưa xác định đã tải game thành công - Thử lại lần {current_try}.")
        return handle_post_login(worker, account, device, ocr_client, current_try + 1)

    worker.log_message.emit(
        f"[{account.username}] Không nhận diện được trạng thái hậu đăng nhập từ {len(templates)} template."
    )
    return False, "Không xác định được trạng thái sau đăng nhập"


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
            "không phát hiện được wrong_username_or_pass; đăng nhập thành công theo quy tắc hiện tại."
        )
        return True, None

    # get_templates tự đọc cấu hình, cắt ảnh và cache template đã tải.
    template_names = (
        _TEMPLATE_ACCOUNT_THONG_TIN_DANG_NHAP_KHONG_DUNG,
        _TEMPLATE_ACCOUNT_WAITING,
        _TEMPLATE_ACCOUNT_TRANG_CA_NHAN,
    )
    templates = get_templates(template_names)

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
                grayscale=template.grayscale,
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
            template=template,
            match=match,
        )
        if template.id == "thong_tin_dang_nhap_khong_dung":
            reason = "Thông tin đăng nhập không đúng"
            worker.log_message.emit(
                f"[{account.username}] Đăng nhập thất bại: phát hiện template wrong_username_or_pass."
            )
            return False, reason

    worker.log_message.emit(
        f"[{account.username}] Đăng nhập thành công."
    )
    return True, None

def prepare_login(
    worker, account, device, ocr_client
) -> tuple[bool, str | None]:
    """Nhận diện và xử lý trạng thái màn hình trước khi đăng nhập."""
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return False, "Đã dừng theo yêu cầu"

    template_names = (
        _TEMPLATE_ACCOUNT_DICH_QUAN_TAP_KICH,
        _TEMPLATE_ACCOUNT_DANG_NHAP,
        _TEMPLATE_ACCOUNT_WAITING,
        _TEMPLATE_ACCOUNT_TRANG_CA_NHAN,
        _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
        _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
        _TEMPLATE_ACCOUNT_MAN_HINH_CHINH,
    )
    templates = get_templates(template_names)

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(
            np.asarray(screenshot), cv2.COLOR_RGB2BGR
        )
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.username}] Không chụp được màn hình tiền đăng nhập: {exc}"
        )
        return False, "Không xác minh được trạng thái trước đăng nhập"

    detected_state = None
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
            context=f"[{account.username}] Tiền đăng nhập:",
            template=template,
            match=match,
        )
        detected_state = template.id
        break

    if detected_state == "dich_quan_tap_kich":
        worker.log_message.emit(
            f"[{account.username}] Phát hiện Địch Quân Tập Kích; đang đóng cửa sổ."
        )
        try:
            ocr_client.tap_ocr_target("close_dich_quan_tap_kich")
        except Exception as exc:
            worker.log_message.emit(
                f"[{account.username}] Không đóng được cửa sổ Địch Quân Tập Kích: {exc}"
            )
            return False, "Không đóng được cửa sổ Địch Quân Tập Kích"
        time.sleep(1)
        return prepare_login(worker, account, device, ocr_client)

    if detected_state == "dang_nhap":
        return True, None

    if detected_state in ("trang_ca_nhan", "man_hinh_chinh"):
        worker.log_message.emit(
            f"[{account.username}] Đang ở màn hình profile; gọi quy trình đăng xuất."
        )
        logout_result, logout_error = logout_account(
            worker, account, device, ocr_client
        )
        if logout_result is not True:
            return logout_result, logout_error
        return prepare_login(worker, account, device, ocr_client)

    if detected_state == "waiting":
        worker.log_message.emit(
            f"[{account.username}] Màn hình đang chờ; kiểm tra lại sau 3 giây."
        )
        time.sleep(3)
        return prepare_login(worker, account, device, ocr_client)

    if detected_state == "cap_nhat_thong_tin" or detected_state == "close_cap_nhat_thong_tin":
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
        return prepare_login(worker, account, device, ocr_client)

    worker.log_message.emit(
        f"[{account.username}] Không nhận diện được trạng thái tiền đăng nhập."
    )
    return False, "Không xác định được trạng thái trước đăng nhập"

def login_account(
    worker, account, device, ocr_client
) -> tuple[bool | None, str | None]:
    """Điều phối toàn bộ quy trình đăng nhập tài khoản.

    Trả về (True, None) khi đã xác nhận vào game,
    (False, error) khi đăng nhập hoặc xác minh thất bại,
    và (None, None) khi worker yêu cầu dừng/tạm dừng.
    """
    prepared, error = prepare_login(worker, account, device, ocr_client)
    if not prepared:
        return False, error

    if not submit_login_form(worker, account, device, ocr_client):
        return None, None

    verified, error = verify_login(worker, account, device, ocr_client)
    if verified is not True:
        return verified, error

    return handle_post_login(worker, account, device, ocr_client)
