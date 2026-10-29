"""Điều phối các bước thuộc màn hình [Quân đoàn]."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
)
from dctq_auto.tasks.common.guild import task_close_guild, task_open_guild

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

        steps_run(worker, account, steps, device, ocr_client, log)
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.username}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
            except Exception as exc:
                log(f"[{account.username}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")

    return steps

def steps_run( worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    selected_steps = {
        step for step in (_GUILD_STEP_IDS) if step in steps
    }
    if not selected_steps:
        return steps

    template_names = get_template_names(steps)
    templates = get_templates(template_names)
    # Tiếp tục nhận diện bằng đệ quy sau mỗi thao tác thay đổi màn hình.
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

    return steps

def get_template_names(steps) -> list[str]:
    """Lấy danh sách template cần nhận diện theo các step được chọn."""
    template_names = []

    if _STEP_QUAN_DOAN_BAO_DANH in steps:
        template_names.extend((
            _TEMPLATE_QUAN_DOAN_BAO_DANH,
            _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
        ))

    return template_names