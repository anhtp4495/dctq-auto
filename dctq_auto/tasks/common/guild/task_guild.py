"""Điều phối các Poller thuộc màn hình [Quân đoàn]."""

import importlib
import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_NHAN_THUONG_BOSS,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.guild import task_close_guild, task_open_guild
from dctq_auto.tasks.common.guild.polling import (
    DailyCheckInPoller,
    LuckyBagPoller,
    RationsPoller,
    KnbPoller,
    BlessingPoller,
    BossRewardPoller,
)
from dctq_auto.tasks.common.guild.polling.rations_poller import (
    _RUN_TEMPLATES as _RATION_RUN_TEMPLATES,
    _CLOSE_TEMPLATES as _RATION_CLOSE_TEMPLATES,
)
from dctq_auto.vision.template_store import get_templates


_POLL_TIMEOUT_SECONDS = 180
_POLL_INTERVAL_SECONDS = 0.8

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


def _capture_screen(context):
    """Chụp màn hình hiện tại và chuyển sang BGR."""
    try:
        return cv2.cvtColor(
            np.asarray(context["device"].screenshot()), cv2.COLOR_RGB2BGR
        )
    except Exception as exc:
        context["log"](
            f"[{context['account'].display_name}] [Quân đoàn] "
            f"Không chụp được màn hình: {exc}"
        )
        return None


def _observe_ration(poller, context, templates, template_names):
    screen = _capture_screen(context)
    if screen is None:
        return None
    return poller.check({
        "screen": screen,
        "templates": templates,
        "template_names": template_names,
        "account": context["account"],
        "log": context["log"],
    })


def _handle_ration_observation(observation, poller, context, phase):
    """Xử lý observation Lương thảo; Poller chỉ nhận diện, task_guild thao tác."""
    state = observation["state"]
    account = context["account"]
    log = context["log"]

    if phase == "run":
        if state == "guild_main":
            # Từ màn hình chính Quân đoàn, mở khu vực chức năng.
            x, y = click_match(context["device"], observation["match"])
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                f"Click màn hình chính Quân đoàn tại ({x}, {y})."
            )
        elif state == "not_donated":
            x, y = click_match(context["device"], observation["match"])
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                f"Click nút đóng góp Lương thảo tại ({x}, {y})."
            )
        elif state == "donation_screen":
            x, y = ButtonPositions().get("quan_doan.luong_thao", "dong_gop")
            context["device"].shell(f"input tap {x} {y}")
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                f"Thực hiện đóng góp Lương thảo tại ({x}, {y})."
            )
        elif state in {"stop_quickly", "confirm_stop_quickly"}:
            x, y = click_match(context["device"], observation["match"])
            label = "nút Dùng nhanh" if state == "stop_quickly" else "nút xác nhận Dùng nhanh"
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                f"Click {label} tại ({x}, {y})."
            )
        elif state in {"donated", "buy_rations", "close_donation_screen"}:
            if state == "donated":
                log(f"[{account.display_name}] Đã xác nhận đóng góp Lương thảo.")
            elif state == "buy_rations":
                log(
                    f"[{account.display_name}] Xuất hiện thông báo lấy thêm "
                    "Lương thảo bằng KNB; bỏ qua thao tác Dùng nhanh."
                )
            return "success"
        else:
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                f"Chưa nhận diện được trạng thái đóng góp ({state})."
            )
        return "continue"

    if state == "guild_main":
        log(
            f"[{account.display_name}] Đã xác nhận đóng màn hình đóng góp "
            "và trở về màn hình chính Quân đoàn."
        )
        return "completed"
    if state == "close_donation_screen":
        x, y = click_match(context["device"], observation["match"])
        log(
            f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
            f"Click nút đóng màn hình đóng góp tại ({x}, {y})."
        )
    else:
        log(
            f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
            f"Chưa thấy màn hình chính hoặc nút đóng ({state})."
        )
    return "continue"


def _run_rations_poller(poller, context):
    """Polling và xử lý Lương thảo trong task_guild, tối đa 3 phút."""
    account = context["account"]
    log = context["log"]
    phase = "run"
    template_names = _RATION_RUN_TEMPLATES
    templates = get_templates(template_names)
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    log(f"[{account.display_name}] Bắt đầu đóng góp Lương thảo.")
    while time.monotonic() < deadline:
        if not context["worker"]._wait_if_paused():
            log(f"[{account.display_name}] Đóng góp Lương thảo đã dừng theo yêu cầu.")
            return False

        observation = _observe_ration(poller, context, templates, template_names)
        if observation is None:
            return False

        result = _handle_ration_observation(
            observation, poller, context, phase
        )
        if result == "success":
            phase = "close"
            template_names = _RATION_CLOSE_TEMPLATES
            templates = get_templates(template_names)
        elif result == "completed":
            log(f"[{account.display_name}] Hoàn tất tác vụ đóng góp Lương thảo.")
            return True

        time.sleep(_POLL_INTERVAL_SECONDS)

    log(
        f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
        "Quá thời gian polling tối đa 3 phút; giữ nguyên step."
    )
    return False


def _run_legacy_task(poller, context):
    """Điều phối tạm thời category chưa chuyển sang observation handler."""
    module = importlib.import_module(
        f"dctq_auto.tasks.common.guild.{poller.task_module}"
    )
    return module.run(
        context["worker"],
        context["account"],
        context["steps"],
        context["device"],
        context.get("ocr_client"),
        context["log"],
        screenshot=context.get("screenshot"),
    )


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Mở Quân đoàn, điều phối từng task và đóng màn hình."""
    if not _GUILD_STEP_IDS.intersection(steps):
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

    try:
        if not task_open_guild.run(
            worker, account, device, ocr_client, log, screenshot=screenshot
        ):
            log(f"[{account.display_name}] Không mở được màn hình [Quân đoàn]; giữ nguyên các bước.")
            return steps

        for poller in create_pollers(context):
            try:
                if isinstance(poller, RationsPoller):
                    if _run_rations_poller(poller, context):
                        if poller.step_id in steps:
                            steps.remove(poller.step_id)
                else:
                    steps = _run_legacy_task(poller, context)
                    context["steps"] = steps
            except Exception as exc:
                log(
                    f"[{account.display_name}] [Quân đoàn] "
                    f"{poller.category_key} thất bại: {exc}"
                )
        return steps
    finally:
        try:
            closed = task_close_guild.run(worker, account, device, ocr_client, log)
            if not closed:
                log(f"[{account.display_name}] Cảnh báo: chưa xác nhận thoát được màn hình [Quân đoàn].")
        except Exception as exc:
            log(f"[{account.display_name}] Lỗi khi thoát màn hình [Quân đoàn]: {exc}")
