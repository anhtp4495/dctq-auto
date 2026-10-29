"""Điều phối các bước thuộc màn hình [Quân đoàn]."""

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB,
    _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
    _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
)
from dctq_auto.tasks.common.guild import (
    task_blessing,
    task_close_guild,
    task_daily_check_in,
    task_donate_rations,
    task_knb,
    task_lucky_bag,
    task_open_guild,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_GUILD_STEP_IDS = {
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
}


def run(worker, account, steps, device, ocr_client, log, screenshot=None):
    """Mở Quân đoàn, chạy các bước được chọn, rồi đóng màn hình.

    Các bước thành công được loại khỏi danh sách steps tại chỗ. Bước thất bại
    và các bước chưa chạy được giữ lại để luồng Clone có thể thử lại.
    """
    guild_open_attempted = False
    try:
        selected_steps = _GUILD_STEP_IDS.intersection(steps)
        if not selected_steps:
            return steps

        guild_open_attempted = True
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.username}] Không mở được màn hình [Quân đoàn]; giữ nguyên các bước.")
            return steps

        steps_run(worker, account, steps, device, ocr_client, log, screenshot=screenshot)
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")

    return steps


def steps_run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Nhận diện trạng thái Quân đoàn và chạy các step có thể xác định."""
    selected_steps = {step for step in _GUILD_STEP_IDS if step in steps}
    if not selected_steps:
        return steps

    template_names = get_template_names(selected_steps)
    templates = get_templates(template_names)
    if not templates:
        log(f"[{account.username}] Chưa có template hợp lệ cho các bước Quân đoàn; giữ nguyên step.")
        return steps

    if not worker._wait_if_paused():
        log(f"[{account.username}] Quân đoàn đã dừng theo yêu cầu.")
        return steps

    try:
        if screenshot is None:
            screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        log(f"[{account.username}] Không chụp được màn hình để nhận diện Quân đoàn: {exc}")
        return steps

    template_name, template, match = _find_template(
        screen_bgr, templates, template_names, account, log
    )
    if template_name is None:
        log(f"[{account.username}] Không nhận diện được trạng thái Quân đoàn; giữ lại step chưa chạy.")
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH:
        # Màn hình chính chỉ xác nhận đang ở Quân đoàn, không đồng nghĩa các step đã hoàn tất.
        # Tiếp tục giữ các step để chờ template trạng thái cụ thể của từng tác vụ.
        log(f"[{account.username}] Đang ở màn hình chính Quân đoàn; chưa xác định step cần thực hiện.")
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH:
        if _STEP_QUAN_DOAN_BAO_DANH not in selected_steps:
            return steps
        try:
            success = task_daily_check_in.run(worker, device, ocr_client)
        except Exception as exc:
            log(f"[{account.username}] Báo danh Quân đoàn thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step báo danh Quân đoàn để thử lại.")
            return steps
        steps.remove(_STEP_QUAN_DOAN_BAO_DANH)
        return steps_run(worker, account, steps, device, ocr_client, log)

    if template_name == _TEMPLATE_QUAN_DOAN_DA_BAO_DANH:
        # Template xác nhận đã báo danh; hoàn tất step mà không thao tác lần nữa.
        if _STEP_QUAN_DOAN_BAO_DANH in steps:
            steps.remove(_STEP_QUAN_DOAN_BAO_DANH)
            return steps_run(worker, account, steps, device, ocr_client, log)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC:
        if _STEP_QUAN_DOAN_TUI_PHUC not in selected_steps:
            return steps
        try:
            success = task_lucky_bag.run(worker, device, ocr_client)
        except Exception as exc:
            log(f"[{account.username}] Nhận Túi phúc thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step Túi phúc để thử lại.")
            return steps
        steps.remove(_STEP_QUAN_DOAN_TUI_PHUC)
        return steps_run(worker, account, steps, device, ocr_client, log)

    if template_name == _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC:
        if _STEP_QUAN_DOAN_TUI_PHUC in steps:
            steps.remove(_STEP_QUAN_DOAN_TUI_PHUC)
            return steps_run(worker, account, steps, device, ocr_client, log)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_CAU_VAN:
        if _STEP_QUAN_DOAN_CAU_VAN not in selected_steps:
            return steps
        try:
            success = task_blessing.run(worker, device, ocr_client)
        except Exception as exc:
            log(f"[{account.username}] Cầu vận Quân đoàn thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step Cầu vận để thử lại.")
            return steps
        steps.remove(_STEP_QUAN_DOAN_CAU_VAN)
        return steps_run(worker, account, steps, device, ocr_client, log)

    if template_name == _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO:
        if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO not in selected_steps:
            return steps
        try:
            success = task_donate_rations.run(worker, device, ocr_client)
        except Exception as exc:
            log(f"[{account.username}] Đóng góp lương thảo thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step đóng góp lương thảo để thử lại.")
            return steps
        steps.remove(_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO)
        return steps_run(worker, account, steps, device, ocr_client, log)

    if template_name == _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO:
        if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in steps:
            steps.remove(_STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO)
            return steps_run(worker, account, steps, device, ocr_client, log)
        return steps

    if template_name == _TEMPLATE_QUAN_DOAN_DONG_GOP_KNB:
        if _STEP_QUAN_DOAN_DONG_GOP_KNB not in selected_steps:
            return steps
        # TODO: Thêm xác nhận trạng thái đã đóng góp KNB; hiện chỉ có template "chưa đóng góp".
        try:
            success = task_knb.run(worker, device, ocr_client)
        except Exception as exc:
            log(f"[{account.username}] Đóng góp KNB thất bại: {exc}")
            success = False
        if not success:
            log(f"[{account.username}] Giữ lại step đóng góp KNB để thử lại.")
            return steps
        steps.remove(_STEP_QUAN_DOAN_DONG_GOP_KNB)
        return steps_run(worker, account, steps, device, ocr_client, log)

    return steps

def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step Quân đoàn được chọn."""
    template_names = []

    if _STEP_QUAN_DOAN_BAO_DANH in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
            _TEMPLATE_QUAN_DOAN_DA_BAO_DANH,
        ))

    if _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
            _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
        ))

    if _STEP_QUAN_DOAN_DONG_GOP_KNB in steps:
        template_names.append(_TEMPLATE_QUAN_DOAN_DONG_GOP_KNB)

    if _STEP_QUAN_DOAN_TUI_PHUC in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_CHUA_NHAN_TUI_PHUC,
            _TEMPLATE_QUAN_DOAN_DA_NHAN_TUI_PHUC,
        ))

    if _STEP_QUAN_DOAN_CAU_VAN in steps:
        template_names.append(_TEMPLATE_QUAN_DOAN_CAU_VAN)

    template_names.append(_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH)
    return template_names


def _find_template(screen_bgr, templates, template_names, account, log):
    """Trả về template khớp đầu tiên theo thứ tự ưu tiên."""
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
