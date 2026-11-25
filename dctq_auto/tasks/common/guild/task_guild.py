"""Điều phối các Poller thuộc màn hình [Quân đoàn]."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_GOP_KNB,
    _STEP_QUAN_DOAN_BAO_DANH,
    _STEP_QUAN_DOAN_CAU_VAN,
    _STEP_QUAN_DOAN_DONG_GOP_KNB,
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _STEP_QUAN_DOAN_TUI_PHUC,
    _STEP_QUAN_DOAN_NHAN_THUONG_BOSS,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH,
    _TEMPLATE_QUAN_DOAN_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
    _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
    _TEMPLATE_QUAN_DOAN_THOAT_MAN_HINH_CAU_VAN,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.tasks.common.battle.battle_utils import click_match, swipe
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
from dctq_auto.tasks.common.guild.polling.knb_poller import (
    _RUN_TEMPLATES as _KNB_RUN_TEMPLATES,
    _CLOSE_TEMPLATES as _KNB_CLOSE_TEMPLATES,
)
from dctq_auto.vision.template_matching import TemplateMatch
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


def _observe_poller(poller, context, templates, template_names):
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
        if state == "not_donated":
            x, y = click_match(context["device"], observation["match"])
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                f"Click nút đóng góp Lương thảo tại ({x}, {y})."
            )
            return "contribution_handled"
        elif state == "donated":
            log(f"[{account.display_name}] Đã xác nhận đóng góp Lương thảo.")
            return "success"
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
        elif state in {"buy_rations", "close_donation_screen"}:
            if state == "buy_rations":
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
    # Ban đầu tuyệt đối không dò màn hình chính vì template này xuất hiện
    # trên phần lớn màn hình. Chỉ bật nhận diện sau khi đã xử lý CHƯA ĐÓNG GÓP
    # hoặc xác nhận ĐÃ ĐÓNG GÓP ít nhất một lần.
    contribution_handled = False
    template_names = _RATION_RUN_TEMPLATES
    templates = get_templates(template_names)
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    log(f"[{account.display_name}] Bắt đầu đóng góp Lương thảo.")
    while time.monotonic() < deadline:
        if not context["worker"]._wait_if_paused():
            log(f"[{account.display_name}] Đóng góp Lương thảo đã dừng theo yêu cầu.")
            return False

        observation = _observe_poller(poller, context, templates, template_names)
        if observation is None:
            return False

        result = _handle_ration_observation(
            observation, poller, context, phase
        )
        if result == "contribution_handled":
            if not contribution_handled:
                contribution_handled = True
                template_names = (
                    *_RATION_RUN_TEMPLATES,
                    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
                )
                templates = get_templates(template_names)
        elif result == "success":
            if observation["state"] == "donated":
                contribution_handled = True
            phase = "close"
            # Chỉ cho phép dùng template màn hình chính làm dấu kết thúc
            # sau khi CHƯA ĐÓNG GÓP đã được click hoặc ĐÃ ĐÓNG GÓP được xác nhận.
            template_names = (
                _RATION_CLOSE_TEMPLATES
                if contribution_handled
                else _RATION_CLOSE_TEMPLATES[:-1]
            )
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


def _run_knb_poller(poller, context):
    """Polling và điều phối đóng góp KNB; Poller chỉ nhận diện trạng thái."""
    account = context["account"]
    log = context["log"]
    phase = "run"
    small_donation_count = 0
    last_small_donation_template = None
    template_names = _KNB_RUN_TEMPLATES
    _KNB_DONATION_CLOSE_TEMPLATE = _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_GOP_KNB
    templates = get_templates(template_names)
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    log(f"[{account.display_name}] Bắt đầu đóng góp KNB.")
    while time.monotonic() < deadline:
        if not context["worker"]._wait_if_paused():
            log(f"[{account.display_name}] Đóng góp KNB đã dừng theo yêu cầu.")
            return False

        observation = _observe_poller(poller, context, templates, template_names)
        if observation is None:
            return False

        state = observation["state"]
        if phase == "run":
            if state == "entry":
                x, y = click_match(context["device"], observation["match"])
                log(
                    f"[{account.display_name}] [Quân đoàn] [KNB] "
                    f"Click trung tâm nút đóng góp KNB tại ({x}, {y})."
                )
            elif state in {"donate_10", "donate_20"}:
                template_name = observation["template_name"]
                if template_name == last_small_donation_template:
                    time.sleep(_POLL_INTERVAL_SECONDS)
                    continue
                x, y = click_match(context["device"], observation["match"])
                last_small_donation_template = template_name
                small_donation_count += 1
                log(
                    f"[{account.display_name}] [Quân đoàn] [KNB] "
                    f"Click mức {10 if state == 'donate_10' else 20} KNB "
                    f"tại ({x}, {y}); lần {small_donation_count}/3."
                )
                if state == "donate_20" or small_donation_count >= 3:
                    phase = "close_screen"
                    # Nút đóng là tùy chọn: nếu xuất hiện thì click, nếu không
                    # có thì chấp nhận màn hình chính làm dấu hoàn tất.
                    template_names = (
                        _KNB_DONATION_CLOSE_TEMPLATE,
                        *_KNB_CLOSE_TEMPLATES,
                    )
                    templates = get_templates(template_names)
                    log(
                        f"[{account.display_name}] Đã hoàn tất đóng góp KNB; "
                        "chờ nút đóng màn hình đóng góp hoặc màn hình chính Quân đoàn."
                    )
            elif state == "insufficient_conditions":
                log(
                    f"[{account.display_name}] Không đủ điều kiện đóng góp KNB; "
                    "chờ xác nhận màn hình chính Quân đoàn."
                )
                phase = "close"
                template_names = _KNB_CLOSE_TEMPLATES
                templates = get_templates(template_names)
            else:
                log(
                    f"[{account.display_name}] [Quân đoàn] [KNB] "
                    f"Chưa nhận diện được trạng thái đóng góp ({state})."
                )
        elif phase == "close_screen" and state == "close_donation_screen":
            x, y = click_match(context["device"], observation["match"])
            log(
                f"[{account.display_name}] [Quân đoàn] [KNB] "
                f"Click trung tâm nút đóng màn hình đóng góp tại ({x}, {y})."
            )
            phase = "close"
            template_names = _KNB_CLOSE_TEMPLATES
            templates = get_templates(template_names)
        elif state == "guild_main":
            log(
                f"[{account.display_name}] Đã xác nhận màn hình chính Quân đoàn; "
                "hoàn tất đóng góp KNB."
            )
            return True
        else:
            waiting_for = (
                "nút đóng màn hình đóng góp hoặc màn hình chính Quân đoàn"
                if phase == "close_screen"
                else "màn hình chính Quân đoàn"
            )
            log(
                f"[{account.display_name}] [Quân đoàn] [KNB] "
                f"Đang chờ {waiting_for} ({state})."
            )

        time.sleep(_POLL_INTERVAL_SECONDS)

    log(
        f"[{account.display_name}] [Quân đoàn] [KNB] "
        "Quá thời gian polling tối đa 3 phút; giữ nguyên step."
    )
    return False



def _handle_daily_check_in_observation(observation, context, phase, templates):
    """Xử lý observation báo danh; Poller chỉ nhận diện trạng thái."""
    account = context["account"]
    device = context["device"]
    log = context["log"]
    state = observation["state"]

    if state == "checked_in":
        if phase == "run":
            log(
                f"[{account.display_name}] Đã báo danh Quân đoàn; "
                "chờ xác nhận màn hình chính."
            )
            return "close"
    elif state == "not_checked_in":
        if phase == "run":
            x, y = click_match(device, observation["match"])
            log(
                f"[{account.display_name}] Click trung điểm template chưa báo danh "
                f"tại ({x}, {y}); chờ xác nhận màn hình chính."
            )
            return "close"
    elif state == "guild_main":
        if phase == "close":
            log(
                f"[{account.display_name}] Đã xác nhận màn hình chính Quân đoàn "
                "sau thao tác báo danh; hoàn tất."
            )
            return "completed"
        try:
            search_top, search_left, search_right, search_bottom = (
                templates[_TEMPLATE_QUAN_DOAN_CHUA_BAO_DANH].search_rect
            )
            search_match = TemplateMatch(
                search_top,
                search_left,
                search_right,
                search_bottom,
                1.0,
            )
            x, y = click_match(device, search_match)
            log(
                f"[{account.display_name}] Màn hình chính Quân đoàn đang hiển thị; "
                f"click trung điểm vùng search_rect của template chưa báo danh "
                f"tại ({x}, {y}); chờ nhận diện lại màn hình chính để kết thúc."
            )
            return "close"
        except Exception as exc:
            log(
                f"[{account.display_name}] Không click được trung điểm vùng "
                f"search_rect của template chưa báo danh: {exc}"
            )
            return "failed"

    return "continue"


def _handle_blessing_observation(observation, context, phase):
    """Xử lý observation Cầu vận; trả về kết quả, phase và bộ template tiếp theo."""
    account = context["account"]
    log = context["log"]
    device = context["device"]
    state = observation["state"]
    match = observation.get("match")

    if state == "entry":
        x, y = click_match(device, match)
        log(f"[{account.display_name}] Mở lối vào Cầu vận tại ({x}, {y}).")
        # Template màn hình chính cùng xuất hiện với lối vào, chỉ bật sau click.
        template_names = (
            _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
            _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
            _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
            _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
        )
        return "continue", phase, template_names, get_templates(template_names)

    if state == "can_bless":
        x, y = click_match(device, match)
        log(f"[{account.display_name}] Thực hiện Cầu vận tại ({x}, {y}).")
    elif state in {"no_turns_1", "no_turns_2"}:
        phase = "close"
        log(f"[{account.display_name}] Đã xác nhận Cầu vận hết lượt.")
        template_names = (
            _TEMPLATE_QUAN_DOAN_THOAT_MAN_HINH_CAU_VAN,
            _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
        )
        return "continue", phase, template_names, get_templates(template_names)
    elif state == "exit_blessing":
        x, y = click_match(device, match)
        log(f"[{account.display_name}] Thoát màn hình Cầu vận tại ({x}, {y}).")
        template_names = (_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,)
        return "continue", phase, template_names, get_templates(template_names)
    elif state == "guild_main":
        log(
            f"[{account.display_name}] Đã xác nhận màn hình chính Quân đoàn; "
            "hoàn tất Cầu vận."
        )
        return "completed", phase, None, None

    return "continue", phase, None, None


def _run_remaining_poller(poller, context):
    """Điều phối các poller còn lại; mọi nhận diện đều qua observation."""
    account = context["account"]
    log = context["log"]
    device = context["device"]
    worker = context["worker"]
    state_by_template = poller.state_by_template
    # Các template màn hình tổng quan dễ xuất hiện thường xuyên nên luôn
    # được kiểm tra sau các trạng thái thao tác cụ thể.
    template_names = tuple(
        name for name in state_by_template
        if state_by_template[name] not in {"guild_main", "boss_main"}
    )
    if isinstance(poller, BossRewardPoller):
        template_names += tuple(
            name for name in state_by_template
            if state_by_template[name] == "boss_main"
        )
    template_names += tuple(
        name for name in state_by_template
        if state_by_template[name] == "guild_main"
    )
    templates = get_templates(template_names)
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
    phase = "run"
    lucky_positions = None
    lucky_closed = False
    boss_reward_clicked = False
    boss_empty_swipes = 0

    if isinstance(poller, BlessingPoller):
        # Ban đầu chỉ nhận diện lối vào và trạng thái Cầu vận; chưa xét
        # guild_main vì template này cùng xuất hiện với lối vào.
        template_names = (
            _TEMPLATE_QUAN_DOAN_CAU_VAN,
            _TEMPLATE_QUAN_DOAN_CO_THE_CAU_VAN,
            _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN1,
            _TEMPLATE_QUAN_DOAN_HET_LUOT_CAU_VAN2,
        )
        templates = get_templates(template_names)
        log(f"[{account.display_name}] Bắt đầu Cầu vận Quân đoàn.")
    elif isinstance(poller, DailyCheckInPoller):
        template_names = (
            *[name for name in template_names if state_by_template[name] != "guild_main"],
            *[name for name in template_names if state_by_template[name] == "guild_main"],
        )
        templates = get_templates(template_names)
        log(f"[{account.display_name}] Bắt đầu báo danh Quân đoàn.")
    elif isinstance(poller, LuckyBagPoller):
        lucky_positions = [
            ButtonPositions().get("quan_doan.tui_phuc", "tuong"),
            ButtonPositions().get("quan_doan.tui_phuc", "truong_thanh"),
            ButtonPositions().get("quan_doan.tui_phuc", "knb"),
        ]
        log(f"[{account.display_name}] Bắt đầu nhận Túi phúc Quân đoàn.")
    elif isinstance(poller, BossRewardPoller):
        log(f"[{account.display_name}] Bắt đầu nhận thưởng Boss Quân đoàn.")

    while time.monotonic() < deadline:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Tác vụ {poller.category_key} đã dừng theo yêu cầu.")
            return False

        observation = _observe_poller(poller, context, templates, template_names)
        if observation is None:
            return False
        state = observation["state"]
        match = observation.get("match")

        if isinstance(poller, DailyCheckInPoller):
            result = _handle_daily_check_in_observation(
                observation,
                context,
                phase,
                templates,
            )
            if result == "close":
                phase = "close"
            elif result == "completed":
                return True
            elif result == "failed":
                return False

        elif isinstance(poller, BlessingPoller):
            result, phase, next_template_names, next_templates = (
                _handle_blessing_observation(observation, context, phase)
            )
            if result == "completed":
                return True
            if next_template_names is not None:
                template_names = next_template_names
                templates = next_templates

        elif isinstance(poller, LuckyBagPoller):
            if state in {"already_received", "not_received"}:
                if lucky_positions is None:
                    lucky_positions = []
                x, y = click_match(device, match)
                log(f"[{account.display_name}] Mở Túi phúc tại ({x}, {y}).")
            elif state == "detail":
                try:
                    x, y = ButtonPositions().get("quan_doan.tui_phuc", "dong_man_hinh")
                    device.shell(f"input tap {x} {y}")
                    log(f"[{account.display_name}] Đóng chi tiết Túi phúc tại ({x}, {y}).")
                except Exception as exc:
                    log(f"[{account.display_name}] Không đóng được chi tiết Túi phúc: {exc}")
                    return False
            elif state == "receive_screen":
                if lucky_positions:
                    x, y = lucky_positions.pop(0)
                    try:
                        device.shell(f"input tap {x} {y}")
                        log(f"[{account.display_name}] Nhận Túi phúc tại ({x}, {y}).")
                    except Exception as exc:
                        log(f"[{account.display_name}] Không nhận được Túi phúc: {exc}")
                        return False
                else:
                    try:
                        x, y = ButtonPositions().get("quan_doan.tui_phuc", "dong_man_hinh")
                        device.shell(f"input tap {x} {y}")
                        lucky_closed = True
                        log(f"[{account.display_name}] Đóng màn hình nhận Túi phúc tại ({x}, {y}).")
                    except Exception as exc:
                        log(f"[{account.display_name}] Không đóng được màn hình Túi phúc: {exc}")
                        return False
            elif state == "guild_main" and lucky_closed:
                return True

        elif isinstance(poller, BossRewardPoller):
            if state == "guild_boss_entry":
                x, y = click_match(device, match)
                log(f"[{account.display_name}] Mở lối vào Boss Quân đoàn tại ({x}, {y}).")
            elif state == "boss_main":
                try:
                    start = ButtonPositions().get("quan_doan", "item_2")
                    end = ButtonPositions().get("quan_doan", "item_1")
                    swipe(device, start, end, account=account, log=log, duration_ms=500)
                    log(f"[{account.display_name}] Vuốt danh sách Boss để tìm thưởng.")
                except Exception as exc:
                    log(f"[{account.display_name}] Không vuốt được danh sách Boss: {exc}")
                    return False
            elif state == "reward_available_entry":
                x, y = click_match(device, match)
                log(f"[{account.display_name}] Mở lối nhận thưởng Boss tại ({x}, {y}).")
            elif state == "reward_entrance":
                x, y = click_match(device, match)
                log(f"[{account.display_name}] Mở màn hình nhận thưởng Boss tại ({x}, {y}).")
            elif state == "reward_screen":
                try:
                    start = ButtonPositions().get("quan_doan", "boss_item_2")
                    end = ButtonPositions().get("quan_doan", "boss_item_1")
                    swipe(device, start, end, account=account, log=log, duration_ms=500)
                    boss_empty_swipes += 1
                    log(
                        f"[{account.display_name}] Vuốt danh sách thưởng Boss "
                        f"({boss_empty_swipes}/2)."
                    )
                    if boss_empty_swipes >= 2:
                        phase = "close_boss"
                except Exception as exc:
                    log(f"[{account.display_name}] Không vuốt được danh sách thưởng Boss: {exc}")
                    return False
            elif state == "ready_to_claim":
                log(f"[{account.display_name}] Đã vào màn hình chuẩn bị nhận thưởng Boss.")
            elif state == "claim_button":
                x, y = click_match(device, match)
                boss_reward_clicked = True
                boss_empty_swipes = 0
                log(f"[{account.display_name}] Nhận thưởng Boss tại ({x}, {y}).")
            elif state == "exit_reward_screen":
                x, y = click_match(device, match)
                phase = "close_boss"
                log(f"[{account.display_name}] Đóng màn hình nhận thưởng Boss tại ({x}, {y}).")
            elif state == "exit_boss_screen":
                x, y = click_match(device, match)
                phase = "close_boss"
                log(f"[{account.display_name}] Thoát màn hình Boss tại ({x}, {y}).")
            elif state == "guild_main" and phase == "close_boss":
                return True
            elif state == "guild_main" and not boss_reward_clicked:
                # Boss không còn lối nhận thưởng: xem như đã nhận từ trước.
                return True

        time.sleep(_POLL_INTERVAL_SECONDS)

    log(
        f"[{account.display_name}] [Quân đoàn] [{poller.category_key}] "
        "Quá thời gian polling tối đa 3 phút; giữ nguyên step."
    )
    return False



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
                elif isinstance(poller, KnbPoller):
                    if _run_knb_poller(poller, context):
                        if poller.step_id in steps:
                            steps.remove(poller.step_id)
                else:
                    if _run_remaining_poller(poller, context):
                        if poller.step_id in steps:
                            steps.remove(poller.step_id)
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
