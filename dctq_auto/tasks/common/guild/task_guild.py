"""Điều phối các Poller thuộc màn hình [Quân đoàn]."""

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_NHAN_THUONG_BOSS,
)
from dctq_auto.tasks.common.guild import task_close_guild, task_open_guild
from dctq_auto.tasks.common.guild.polling import (
    DailyCheckInPoller,
    LuckyBagPoller,
    RationsPoller,
    KnbPoller,
    BlessingPoller,
    BossRewardPoller,
)


_GUILD_STEP_IDS = {
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_NHAN_THUONG_BOSS,
}

_GUILD_POLLERS = (
    DailyCheckInPoller,
    LuckyBagPoller,
    RationsPoller,
    KnbPoller,
    BlessingPoller,
    BossRewardPoller,
)


def create_pollers(context):
    """Tạo các Poller có step được chọn; task không được chọn sẽ bị bỏ qua."""
    pollers = []
    for poller_type in _GUILD_POLLERS:
        poller = poller_type.create(context)
        if poller is not None:
            pollers.append(poller)
    return pollers


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Quân đoàn, chạy các Poller được chọn, rồi đóng màn hình."""
    selected_steps = _GUILD_STEP_IDS.intersection(steps)
    if not selected_steps:
        return steps

    context = {
        "worker": worker,
        "account": account,
        "steps": steps,
        "device": device,
        "ocr_client": ocr_client,
        "log": log,
        "screenshot": screenshot,
    }

    guild_open_attempted = False
    try:
        guild_open_attempted = True
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.display_name}] Không mở được màn hình [Quân đoàn]; giữ nguyên các bước.")
            return steps

        for poller in create_pollers(context):
            try:
                steps = poller.run(context)
                context["steps"] = steps
            except Exception as exc:
                log(
                    f"[{account.display_name}] [Quân đoàn] "
                    f"{poller.category_key} thất bại: {exc}"
                )
        return steps
    finally:
        if guild_open_attempted:
            try:
                closed = task_close_guild.run(worker, account, device, ocr_client, log)
                if not closed:
                    log(f"[{account.display_name}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
            except Exception as exc:
                log(f"[{account.display_name}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")
