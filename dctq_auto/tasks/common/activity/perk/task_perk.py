""""Điều phối các tác vụ thuộc màn hình Hoạt động - Phúc lợi."""

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.activity.perk.constants import (
    _STEP_DIEM_DANH,
    _STEP_QUOC_VAN,
    _TEMPLATE_CHUA_CHON_DIEM_DANH,
    _TEMPLATE_CHUA_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DANG_CHON_DIEM_DANH,
    _TEMPLATE_DANG_CHON_HOAT_DONG,
    _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN,
    _TEMPLATE_DANG_CHON_PHUC_LOI,
)
from dctq_auto.tasks.common.activity.perk import (
    task_diem_danh,
    task_le_bao_quoc_van,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


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
        _TEMPLATE_DANG_CHON_HOAT_DONG,
    ))
    return template_names


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template khớp đầu tiên theo thứ tự ưu tiên đã khai báo."""
    for template_name in template_names:
        template = templates.get(template_name)
        if template is None:
            log(f"[{account.username}] Không tải được template {template_name}; bỏ qua.")
            continue
        try:
            match = match_template(
                screen_bgr,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=template.search_rect,
            )
        except (ValueError, cv2.error) as exc:
            log(f"[{account.username}] Lỗi template matching {template_name}: {exc}")
            continue
        if match is not None:
            report_template_match(
                log,
                context=f"[{account.username}]",
                template=template,
                match=match,
            )
            return template_name, template, match
    return None, None, None


def _tap_button(device, button_name, account, log):
    x, y = ButtonPositions().get("hoat_dong", button_name)
    log(f"[{account.username}] Click {button_name} tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def _tap_match_center(device, match, account, log):
    """Click trung điểm vùng template được nhận diện."""
    x = (match.left + match.right) // 2
    y = (match.top + match.bottom) // 2
    log(f"[{account.username}] Click trung điểm template tại ({x}, {y}).")
    device.shell(f"input tap {x} {y}")
    time.sleep(0.7)


def _swipe_buttons(device, source_name, target_name, account, log):
    positions = ButtonPositions()
    x1, y1 = positions.get("hoat_dong", source_name)
    x2, y2 = positions.get("hoat_dong", target_name)
    log(
        f"[{account.username}] Vuốt danh sách Phúc lợi từ "
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
    if not worker._wait_if_paused():
        log(f"[{account.username}] Phúc lợi đã dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện Phúc lợi: {exc}")
        return steps

    template_name, template, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name is None:
        log(f"[{account.username}] Không nhận diện được trạng thái Phúc lợi; giữ lại step chưa chạy.")
        return steps

    if template_name == _TEMPLATE_DANG_CHON_HOAT_DONG:
        try:
            _tap_button(device, "hoat_dong_phuc_loi", account, log)
        except Exception as exc:
            log(f"[{account.username}] Không mở được mục Phúc lợi: {exc}")
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
                f"[{account.username}] Đã hết tọa độ swipe nhưng vẫn ở "
                "màn hình Phúc lợi; dừng và giữ lại step chưa chạy."
            )
            return steps
        try:
            source_name, target_name = swipe_positions.pop(0)
            _swipe_buttons(
                device, source_name, target_name, account, log
            )
        except Exception as exc:
            log(f"[{account.username}] Không điều chỉnh được danh sách Phúc lợi: {exc}")
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
            log(f"[{account.username}] Không chọn được mục Phúc lợi đang hiển thị: {exc}")
            return steps
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=[],
        )

    if template_name == _TEMPLATE_DANG_CHON_LE_BAO_QUOC_VAN:
        if _STEP_QUOC_VAN not in selected_steps:
            log(f"[{account.username}] Đang ở lễ bao Quốc Vận nhưng step này không được chọn.")
            return steps
        try:
            success = bool(task_le_bao_quoc_van.run(worker, account, steps, device, ocr_client, log))
        except Exception as exc:
            log(f"[{account.username}] Nhận lễ bao Quốc Vận thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step {_STEP_QUOC_VAN} để thử lại.")
            return steps
        steps.remove(_STEP_QUOC_VAN)
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=None,
        )
    if template_name == _TEMPLATE_DANG_CHON_DIEM_DANH:
        if _STEP_DIEM_DANH not in selected_steps:
            log(f"[{account.username}] Đang ở Điểm danh nhưng step này không được chọn.")
            return steps
        try:
            success = bool(task_diem_danh.run(worker, account, steps, device, ocr_client, log))
        except Exception as exc:
            log(f"[{account.username}] Điểm danh thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step {_STEP_DIEM_DANH} để thử lại.")
            return steps
        steps.remove(_STEP_DIEM_DANH)
        return run(
            worker, account, steps, device, ocr_client, log,
            screenshot=None, swipe_positions=None,
        )
    return steps
