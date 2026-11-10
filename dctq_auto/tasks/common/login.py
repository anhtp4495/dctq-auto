"""Các thao tác và khai báo task đăng nhập dùng chung."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_ACCOUNT_CAP_NHAT_THONG_TIN,
    _TEMPLATE_ACCOUNT_CLOSE_CAP_NHAT_THONG_TIN,
    _TEMPLATE_ACCOUNT_DANG_NHAP,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_MAIN_CHIEN_TRANH,
    _TEMPLATE_MAIN_TAM_QUOC_LENH,
    _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH,
    _TEMPLATE_ACCOUNT_MAN_HINH_CHINH,
    _TEMPLATE_ACCOUNT_THONG_TIN_DANG_NHAP_KHONG_DUNG,
    _TEMPLATE_ACCOUNT_TRANG_CA_NHAN,
    _TEMPLATE_ACCOUNT_WAITING,
)
from dctq_auto.tasks.base import TaskSpec
from dctq_auto.tasks.common.logout import logout_account
from dctq_auto.tasks.common.close_knowned_dialog import close_knowned_dialog
from dctq_auto.config.button_positions import ButtonPositions
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
        f"[{account.display_name}] Đã gửi yêu cầu đăng nhập; đang xác minh kết quả bằng template matching."
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
    """Xác nhận game đã vào màn hình chính và menu game hoạt động bình thường."""
    if not worker._wait_if_paused():
        worker.log_message.emit("Đã dừng theo yêu cầu.")
        return None, None

    def capture_screen():
        screenshot = device.screenshot()
        return cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)

    def match_main_templates(screen_bgr):
        template_names = (_TEMPLATE_MAIN_CHIEN_TRANH, _TEMPLATE_MAIN_TAM_QUOC_LENH)
        templates = get_templates(template_names)
        detected = []
        for template_name in template_names:
            template = templates.get(template_name)
            if template is None:
                continue
            try:
                match = _match_account_template(screen_bgr, template)
            except (ValueError, cv2.error) as exc:
                worker.log_message.emit(
                    f"[{account.display_name}] Lỗi template matching {template_name}: {exc}"
                )
                continue
            if match is not None:
                report_template_match(
                    worker.log_message.emit,
                    context=f"[{account.display_name}]",
                    template=template,
                    match=match,
                )
                detected.append(template_name)
        return len(detected) == len(template_names)

    try:
        screen_bgr = capture_screen()
    except Exception as exc:
        worker.log_message.emit(
            f"[{account.display_name}] Không chụp được màn hình hậu đăng nhập: {exc}"
        )
        return False, "Không xác minh được trạng thái sau đăng nhập"

    main_template = get_templates((_TEMPLATE_MAIN_QUAN_SU,)).get(_TEMPLATE_MAIN_QUAN_SU)
    if main_template is None:
        close_knowned_dialog(
            worker, account, device, ocr_client, worker.log_message.emit, screen_bgr
        )
        return False, "Không tải được template màn hình Quân Sự"

    try:
        main_match = _match_account_template(screen_bgr, main_template)
    except (ValueError, cv2.error) as exc:
        worker.log_message.emit(
            f"[{account.display_name}] Lỗi nhận diện màn hình Quân Sự: {exc}"
        )
        main_match = None

    if main_match is None:
        if current_try < _MAX_TRY_DETECT_MAIN_SCREEN:
            worker.log_message.emit(
                f"[{account.display_name}] Đang chờ màn hình Quân Sự "
                f"(lần {current_try}/{_MAX_TRY_DETECT_MAIN_SCREEN})."
            )
            time.sleep(1)
            return handle_post_login(
                worker, account, device, ocr_client, current_try + 1
            )

        worker.log_message.emit(
            f"[{account.display_name}] Hết lượt chờ màn hình Quân Sự; "
            "thử đóng dialog đã biết."
        )
        close_knowned_dialog(
            worker, account, device, ocr_client, worker.log_message.emit, screen_bgr
        )
        return False, "Không nhận diện được màn hình Quân Sự"

    report_template_match(
        worker.log_message.emit,
        context=f"[{account.display_name}]",
        template=main_template,
        match=main_match,
    )

    # Menu có thể đang mở hoặc đóng; trạng thái kết thúc bắt buộc phải là mở.
    if not match_main_templates(screen_bgr):
        worker.log_message.emit(
            f"[{account.display_name}] Menu game đang đóng; đang mở menu."
        )
        try:
            tap_x, tap_y = ButtonPositions().get("main", "open_menu_game")
            device.shell(f"input tap {tap_x} {tap_y}")
            time.sleep(1)
            screen_bgr = capture_screen()
        except Exception as exc:
            worker.log_message.emit(
                f"[{account.display_name}] Không thể mở menu game: {exc}"
            )
            close_knowned_dialog(
                worker, account, device, ocr_client, worker.log_message.emit, screen_bgr
            )
            return False, "Không mở được menu game"

    if not match_main_templates(screen_bgr):
        worker.log_message.emit(
            f"[{account.display_name}] Menu game chưa mở hoặc không nhận diện đủ "
            "Chiến Tranh và Tam Quốc Lệnh; thử đóng dialog đã biết."
        )
        close_knowned_dialog(
            worker, account, device, ocr_client, worker.log_message.emit, screen_bgr
        )
        return False, "Không xác nhận được menu game đang mở"

    worker.log_message.emit(
        f"[{account.display_name}] Đăng nhập thành công; menu game đang mở."
    )
    return True, None


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
            f"[{account.display_name}] Không chụp được màn hình xác minh: {exc}; "
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
                f"[{account.display_name}] Lỗi template matching {template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        report_template_match(
            worker.log_message.emit,
            context=f"[{account.display_name}]",
            template=template,
            match=match,
        )
        if template.id == "thong_tin_dang_nhap_khong_dung":
            reason = "Thông tin đăng nhập không đúng"
            worker.log_message.emit(
                f"[{account.display_name}] Đăng nhập thất bại: phát hiện template wrong_username_or_pass."
            )
            return False, reason

    worker.log_message.emit(
        f"[{account.display_name}] Đăng nhập thành công."
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
        _TEMPLATE_THONG_BAO_DICH_QUAN_TAP_KICH,
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
            f"[{account.display_name}] Không chụp được màn hình tiền đăng nhập: {exc}"
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
                f"[{account.display_name}] Lỗi template matching {template_name}: {exc}"
            )
            continue

        if match is None:
            continue

        report_template_match(
            worker.log_message.emit,
            context=f"[{account.display_name}] Tiền đăng nhập:",
            template=template,
            match=match,
        )
        detected_state = template.id
        break

    if detected_state == "thong_bao_bi_tan_cong":
        worker.log_message.emit(
            f"[{account.display_name}] Phát hiện Địch Quân Tập Kích; đang đóng cửa sổ."
        )
        tap_x, tap_y = ButtonPositions().get("main.dich_quan_tap_kich", "dong_man_hinh")
        worker.log_message.emit(
            f"[{account.display_name}] Đóng màn hình Địch Quân Tập Kích "
            f"theo ButtonPositions tại ({tap_x}, {tap_y})."
        )
        device.shell(f"input tap {tap_x} {tap_y}")
        time.sleep(1)
        return prepare_login(worker, account, device, ocr_client)

    if detected_state == "dang_nhap":
        return True, None

    if detected_state in ("trang_ca_nhan", "man_hinh_chinh"):
        worker.log_message.emit(
            f"[{account.display_name}] Đang ở màn hình profile; gọi quy trình đăng xuất."
        )
        logout_result, logout_error = logout_account(
            worker, account, device, ocr_client
        )
        if logout_result is not True:
            return logout_result, logout_error
        return prepare_login(worker, account, device, ocr_client)

    if detected_state == "waiting":
        worker.log_message.emit(
            f"[{account.display_name}] Màn hình đang chờ; kiểm tra lại sau 3 giây."
        )
        time.sleep(3)
        return prepare_login(worker, account, device, ocr_client)

    if detected_state == "cap_nhat_thong_tin" or detected_state == "close_cap_nhat_thong_tin":
        worker.log_message.emit(
            f"[{account.display_name}] Phát hiện hộp thoại cập nhật thông tin; đang đóng hộp thoại."
        )
        try:
            ocr_client.tap_ocr_target("close_cap_nhat_thong_tin_ca_nhan")
        except Exception as exc:
            worker.log_message.emit(
                f"[{account.display_name}] Không đóng được hộp thoại cập nhật thông tin: {exc}"
            )
            return False, "Không đóng được hộp thoại cập nhật thông tin"
        time.sleep(1)
        return prepare_login(worker, account, device, ocr_client)

    worker.log_message.emit(
        f"[{account.display_name}] Không nhận diện được trạng thái tiền đăng nhập."
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

    time.sleep(2)
    return handle_post_login(worker, account, device, ocr_client)
