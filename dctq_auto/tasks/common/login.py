"""Các thao tác và khai báo task đăng nhập dùng chung."""

import json
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


def _load_account_template(
    worker,
    account,
    template_name: str,
    definition,
    config_path: Path,
    source_image: np.ndarray,
    method_names: dict[str, int],
) -> tuple[np.ndarray, float, int] | None:
    """Đọc cấu hình, kiểm tra rect và cắt template; None nếu không hợp lệ."""
    if not isinstance(definition, dict):
        return None

    rect = definition.get("rect")
    if not isinstance(rect, dict):
        worker.log_message.emit(
            f"[{account.username}] Template {template_name} thiếu rect trong {config_path}; bỏ qua."
        )
        return None

    try:
        top = int(rect["top"])
        left = int(rect["left"])
        right = int(rect["right"])
        bottom = int(rect["bottom"])
        threshold = float(definition.get("threshold", 0.85))
        method_name = definition.get("match_method", "TM_CCOEFF_NORMED")
        method = method_names[method_name]
    except (KeyError, TypeError, ValueError):
        worker.log_message.emit(
            f"[{account.username}] Khai báo rect/threshold/match_method của "
            f"template {template_name} không hợp lệ; bỏ qua."
        )
        return None

    source_height, source_width = source_image.shape[:2]
    # Rect dùng thứ tự top/left/right/bottom; right và bottom không bao gồm.
    if (
        top < 0 or left < 0 or right > source_width or bottom > source_height
        or right <= left or bottom <= top
    ):
        worker.log_message.emit(
            f"[{account.username}] Rect của template {template_name} không hợp lệ: "
            f"top={top}, left={left}, right={right}, bottom={bottom}; "
            f"ảnh gốc {source_width}x{source_height}. Bỏ qua template."
        )
        return None

    template_image = source_image[top:bottom, left:right]
    if template_image.size == 0:
        worker.log_message.emit(
            f"[{account.username}] Template {template_name} cắt ra ảnh rỗng; bỏ qua."
        )
        return None

    return template_image, threshold, method


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

    repo_root = Path(__file__).resolve().parents[3]
    config_path = repo_root / "dctq_auto" / "config" / "templates.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        accounts_config = config["screens"]["accounts"]
        source_path = repo_root / accounts_config["source_image"]
        source_image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        if source_image is None:
            raise FileNotFoundError(f"Không đọc được source_image: {source_path}")
        template_definitions = accounts_config["templates"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        worker.log_message.emit(
            f"[{account.username}] Không đọc được cấu hình template đăng nhập "
            f"{config_path}: {exc}. Không phát hiện được template sai thông tin."
        )
        return True, None

    method_names = {
        "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
        "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
        "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
    }

    # Chỉ lấy đúng 4 template trạng thái đăng nhập đã thống nhất từ cấu hình.
    # Kiểm tra wrong_username_or_pass trước để trạng thái khác không che khuất lỗi.
    template_names = (
        "wrong_username_or_pass",
        "waiting",
        "profile",
        "update_information",
    )
    selected_templates = {
        name: template_definitions.get(name) for name in template_names
    }

    for template_name in template_names:
        definition = selected_templates[template_name]
        loaded = _load_account_template(
            worker,
            account,
            template_name,
            definition,
            config_path,
            source_image,
            method_names,
        )
        if loaded is None:
            continue
        template_image, threshold, method = loaded

        try:
            match = match_template(
                screen_bgr,
                template_image,
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

        display_name = definition.get("name", template_name)
        worker.log_message.emit(
            f"[{account.username}] Template {template_name} ({display_name}) khớp "
            f"(score={match.score:.3f}, threshold={threshold:.3f}, rect={match.rect})."
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
