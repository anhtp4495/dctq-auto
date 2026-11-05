""""Điều phối các tác vụ thuộc màn hình Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _STEP_DIEM_DANH,
    _STEP_QUOC_VAN,
    _TEMPLATE_CHUA_CHON_DIEM_DANH,
    _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DANG_CHON_PHUC_LOI,
    _TEMPLATE_CHUA_CHON_PHUC_LOI,
)
from dctq_auto.tasks.common.activity.perk import (
    task_diem_danh,
    task_le_bao_quoc_van,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_TRIES = 6


def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step được chọn."""
    template_names = []

    if _STEP_QUOC_VAN in steps:
        template_names.extend((
            _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
            _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
        ))

    if _STEP_DIEM_DANH in steps:
        template_names.extend((
            _TEMPLATE_DANG_CHON_DIEM_DANH,
            _TEMPLATE_CHUA_CHON_DIEM_DANH,
        ))

    template_names.extend((
        _TEMPLATE_DANG_CHON_PHUC_LOI,
        _TEMPLATE_CHUA_CHON_PHUC_LOI,
    ))
    return template_names


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template khớp đầu tiên theo thứ tự ưu tiên đã khai báo."""
    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            log(f"[{account.display_name}] Không tải được template {template_name}; bỏ qua.")
            continue
        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=template.search_rect,
                grayscale=template.grayscale,
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.display_name}] Lỗi template matching {template_name}: {exc}")
            continue
        if match is not None:
            report_template_match(
                log,
                context=f"[{account.display_name}]",
                template=template,
                match=match,
            )
            return template_name, template, match
    return None, None, None


def _tap_button(device, button_name, account, log):
    x, y = ButtonPositions().get("hoat_dong", button_name)
    log(f"[{account.display_name}] Click {button_name} tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.display_name}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def _swipe_buttons(device, source_name, target_name, account, log):
    positions = ButtonPositions()
    x1, y1 = positions.get("hoat_dong", source_name)
    x2, y2 = positions.get("hoat_dong", target_name)
    log(
        f"[{account.display_name}] Vuốt danh sách Phúc lợi từ "
        f"{source_name} ({x1}, {y1}) đến {target_name} ({x2}, {y2})."
    )
    device.shell(f"input swipe {x1} {y1} {x2} {y2} 400")
    time.sleep(0.7)


def run(
    worker, account, steps, device, ocr_client, log,
    screenshot=None, swipe_positions=None,
) -> list[str]:
    """Nhận diện trạng thái Phúc lợi và chạy các step đã chọn.

    Nếu được truyền screenshot, dùng ảnh đó cho vòng nhận diện đầu tiên.
    swipe_positions là danh sách cặp tên nút (điểm đầu, điểm cuối).
    Nếu không truyền danh sách, chuỗi vuốt mặc định chỉ được khởi tạo khi
    nhận diện đang ở màn hình chọn Phúc lợi.
    """
    # Không sửa danh sách swipe do bên gọi truyền vào.
    if swipe_positions is not None:
        swipe_positions = list(swipe_positions)
    selected_steps = {
        step for step in (_STEP_QUOC_VAN, _STEP_DIEM_DANH) if step in steps
    }
    if not selected_steps:
        return steps

    template_names = get_template_names(steps)
    templates = get_templates(template_names)
    # Tiếp tục nhận diện bằng đệ quy sau mỗi thao tác thay đổi màn hình.
    template_name = template = match = None
    for attempt in range(1, _MAX_TRIES + 1):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Phúc lợi đã dừng theo yêu cầu.")
            return steps

        try:
            current_screenshot = (
                screenshot
                if attempt == 1 and screenshot is not None
                else device.screenshot()
            )
            screen_bgr = cv2.cvtColor(
                np.asarray(current_screenshot), cv2.COLOR_RGB2BGR
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] Không chụp được màn hình để nhận diện "
                f"Phúc lợi (lần thử {attempt}/{_MAX_TRIES}): {exc}"
            )
            if attempt < _MAX_TRIES:
                time.sleep(1.0)
                continue
            return steps

        template_name, template, match = _find_template(
            screen_bgr, templates, template_names, account, log
        )
        if template_name is not None:
            break

        if attempt < _MAX_TRIES:
            log(
                f"[{account.display_name}] Chưa nhận diện được trạng thái Phúc lợi; "
                f"thử lại ({attempt + 1}/{_MAX_TRIES})."
            )
            time.sleep(1.0)

    if template_name is None:
        log(
            f"[{account.display_name}] Không nhận diện được trạng thái Phúc lợi "
            f"sau {_MAX_TRIES} lần thử; giữ lại step chưa chạy."
        )
        return steps

    if template_name == _TEMPLATE_CHUA_CHON_PHUC_LOI:
        try:
            _tap_match_center(device, match, account, log)
        except Exception as exc:
            log(f"[{account.display_name}] Không mở được mục Phúc lợi: {exc}")
            return steps
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=None,
        )
    if template_name == _TEMPLATE_DANG_CHON_PHUC_LOI:
        if swipe_positions is None:
            swipe_positions = [
                ("hoat_dong_phuc_loi_item1", "hoat_dong_phuc_loi_item2"),
                ("hoat_dong_phuc_loi_item1", "hoat_dong_phuc_loi_item2"),
                ("hoat_dong_phuc_loi_item2", "hoat_dong_phuc_loi_item1"),
                ("hoat_dong_phuc_loi_item2", "hoat_dong_phuc_loi_item1"),
            ]
        if len(swipe_positions) == 0:
            log(
                f"[{account.display_name}] Đã hết tọa độ swipe nhưng vẫn ở "
                "màn hình Phúc lợi; dừng và giữ lại step chưa chạy."
            )
            return steps
        try:
            source_name, target_name = swipe_positions.pop(0)
            _swipe_buttons(
                device, source_name, target_name, account, log
            )
        except Exception as exc:
            log(f"[{account.display_name}] Không điều chỉnh được danh sách Phúc lợi: {exc}")
            return steps
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=swipe_positions,
        )
    if template_name in (
        _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
        _TEMPLATE_CHUA_CHON_DIEM_DANH,
    ):
        # Template "chua_chon" xác nhận mục tiêu đang hiển thị nhưng chưa được chọn.
        # Click giữa vùng template rồi nhận diện lại, không tiếp tục chuỗi swipe.
        try:
            _tap_match_center(device, match, account, log)
        except Exception as exc:
            log(f"[{account.display_name}] Không chọn được mục Phúc lợi đang hiển thị: {exc}")
            return steps
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=[],
        )

    if template_name == _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN:
        if _STEP_QUOC_VAN not in selected_steps:
            log(f"[{account.display_name}] Đang ở lễ bao Quốc Vận nhưng step này không được chọn.")
            return steps
        try:
            success = bool(task_le_bao_quoc_van.run(worker, account, steps, device, ocr_client, log))
        except Exception as exc:
            log(f"[{account.display_name}] Nhận lễ bao Quốc Vận thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.display_name}] Giữ lại step {_STEP_QUOC_VAN} để thử lại.")
            return steps
        steps.remove(_STEP_QUOC_VAN)
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=None,
        )
    if template_name == _TEMPLATE_DANG_CHON_DIEM_DANH:
        if _STEP_DIEM_DANH not in selected_steps:
            log(f"[{account.display_name}] Đang ở Điểm danh nhưng step này không được chọn.")
            return steps
        try:
            success = bool(task_diem_danh.run(worker, account, steps, device, ocr_client, log))
        except Exception as exc:
            log(f"[{account.display_name}] Điểm danh thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.display_name}] Giữ lại step {_STEP_DIEM_DANH} để thử lại.")
            return steps
        steps.remove(_STEP_DIEM_DANH)
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=None,
        )
    return steps
