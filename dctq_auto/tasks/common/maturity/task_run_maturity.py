"""Xử lý các ô Trưởng Thành đã được phân loại."""

import time

from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.maturity.polling import create_poller


_POLL_TIMEOUT_SECONDS = 180

_LABELS = {
    "chua_cong": "Chúa công",
    "ve_tuong": "Vệ tướng",
    "than_binh": "Thần binh",
    "chien_hon": "Chiến hồn",
    "tuong_an": "Tướng ấn",
    "than_tuong": "Thần tượng",
    "ban_be": "Bạn bè",
}


def _create_poller(category, context):
    """Tạo poller theo category; category chưa hỗ trợ sẽ được bỏ qua."""
    return create_poller(category, context)


def _handle_lord_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Chúa công."""
    chua_cong_found = observation.get("chua_cong")
    if not chua_cong_found:
        return False

    if (
        chua_cong_found.get("loi_vao") is not None
        and not poller.has_completed_action("loi_vao")
    ):
        found = chua_cong_found["loi_vao"]
        label = "Chiến kỳ"
        action_key = "loi_vao"
    elif chua_cong_found.get("mien_phi") is not None:
        found = chua_cong_found["mien_phi"]
        label = "Giương cờ"
        action_key = "mien_phi"
    elif chua_cong_found.get("thoat") is not None:
        found = chua_cong_found["thoat"]
        label = "Thoát màn hình Chúa công"
        action_key = "thoat"
        poller.waiting_for_main = True
    else:
        return False

    x, y = click_match(context["device"], found)
    context["log"](
        f"[{context['account'].display_name}] [Trưởng thành] [Chúa công] "
        f"Click {label} tại ({x}, {y})."
    )
    poller.record_action(action_key, context)
    return True


def _handle_divine_weapon_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Thần binh."""
    than_binh_found = observation.get("than_binh")
    if not than_binh_found:
        return False

    # Xử lý ngay template đang được phát hiện; Lối vào chỉ click một lần.
    actions = (
        ("loi_vao", "Lối vào Thần binh"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình nhận miễn phí"),
        ("hoi_thanh", "Hồi thành"),
    )
    for key, label in actions:
        if key == "loi_vao" and poller.has_completed_action(key):
            continue
        if key == "loi_vao" and poller.entry_clicked:
            continue
        found = than_binh_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Thần binh] "
            f"Click {label} tại ({x}, {y})."
        )
        poller.record_action(key, context)
        if key == "loi_vao":
            poller.entry_clicked = True
        elif key == "thoat":
            # Sau khi thoát màn hình nhận miễn phí, chỉ tìm nút Hồi thành.
            poller.waiting_for_hall = True
        elif key == "hoi_thanh":
            poller.waiting_for_hall = False
            poller.waiting_for_main = True
        return True

    return False


def _handle_guardian_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Vệ tướng."""
    ve_tuong_found = observation.get("ve_tuong")
    if not ve_tuong_found:
        return False

    actions = (
        ("loi_vao", "Lối vào Vệ tướng"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Vệ tướng"),
    )
    for key, label in actions:
        if key == "loi_vao" and poller.has_completed_action(key):
            continue
        found = ve_tuong_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Vệ tướng] "
            f"Click {label} tại ({x}, {y})."
        )
        poller.record_action(key, context)
        if key == "thoat":
            poller.waiting_for_main = True
        return True

    return False


def _handle_soul_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Chiến hồn."""
    chien_hon_found = observation.get("chien_hon")
    if not chien_hon_found:
        return False

    actions = (
        ("loi_vao", "Lối vào Chiến hồn"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Chiến hồn"),
    )
    for key, label in actions:
        if key == "loi_vao" and poller.has_completed_action(key):
            continue
        found = chien_hon_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Chiến hồn] "
            f"Click {label} tại ({x}, {y})."
        )
        poller.record_action(key, context)
        if key == "thoat":
            poller.waiting_for_main = True
        return True

    return False


def _handle_tuong_an_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Tướng ấn."""
    tuong_an_found = observation.get("tuong_an")
    if not tuong_an_found:
        return False

    actions = (
        ("loi_vao", "Thăm dò lãnh địa"),
        ("tat_ca", "Thăm dò tất cả"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Tướng ấn"),
    )
    for key, label in actions:
        if key == "loi_vao" and poller.has_completed_action(key):
            continue
        if key == "loi_vao" and poller.entry_clicked:
            continue
        found = tuong_an_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Tướng ấn] "
            f"Click {label} tại ({x}, {y})."
        )
        poller.record_action(key, context)
        if key == "loi_vao":
            poller.entry_clicked = True
        elif key == "thoat":
            poller.waiting_for_main = True
        return True

    return False



def _handle_defense_forge_observation(observation, poller, context) -> bool:
    """Handle an observation from the Defense Forge flow."""
    defense_forge_found = observation.get("than_tuong")
    if not defense_forge_found:
        return False

    actions = (
        ("loi_vao", "Lối vào Thần tượng"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình nhận miễn phí"),
        ("hoi_thanh", "Hồi thành"),
    )
    for key, label in actions:
        if key == "loi_vao" and poller.has_completed_action(key):
            continue
        if key == "loi_vao" and poller.entry_clicked:
            continue
        found = defense_forge_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Thần tượng] "
            f"Click {label} tại ({x}, {y})."
        )
        poller.record_action(key, context)
        if key == "loi_vao":
            poller.entry_clicked = True
        elif key == "thoat":
            poller.waiting_for_hall = True
        elif key == "hoi_thanh":
            poller.waiting_for_hall = False
            poller.waiting_for_main = True
        return True

    return False



def _handle_friend_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Bạn bè."""
    friend_found = observation.get("ban_be")
    if not friend_found:
        return False

    actions = (
        ("loi_vao", "Lối vào danh sách bạn bè"),
        ("mien_phi", "Tặng tim"),
        ("thoat", "Thoát màn hình Bạn bè"),
    )
    for key, label in actions:
        if key == "loi_vao" and poller.has_completed_action(key):
            continue
        found = friend_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Bạn bè] "
            f"Click {label} tại ({x}, {y})."
        )
        poller.record_action(key, context)
        if key == "thoat":
            poller.waiting_for_main = True
        return True

    return False

def _run_poller(poller, context) -> bool:
    """Polling tối đa 3 phút hoặc đến khi hoàn tất."""
    account = context["account"]
    log = context["log"]
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        observation = poller.poll(context)
        if observation is None:
            return False

        if poller.waiting_for_main:
            if observation.get("main_maturity") is not None:
                log(
                    f"[{account.display_name}] [Trưởng thành] "
                    "Đã xác nhận quay về màn hình Trưởng Thành."
                )
                poller.finish(context, "success", "Đã hoàn thành")
                return True
            continue

        if observation.get("chua_cong") is not None:
            _handle_lord_observation(observation, poller, context)
        elif observation.get("than_binh") is not None:
            _handle_divine_weapon_observation(observation, poller, context)
        elif observation.get("ve_tuong") is not None:
            _handle_guardian_observation(observation, poller, context)
        elif observation.get("chien_hon") is not None:
            _handle_soul_observation(observation, poller, context)
        elif observation.get("tuong_an") is not None:
            _handle_tuong_an_observation(observation, poller, context)
        elif observation.get("than_tuong") is not None:
            _handle_defense_forge_observation(observation, poller, context)
        elif observation.get("ban_be") is not None:
            _handle_friend_observation(observation, poller, context)

    log(
        f"[{account.display_name}] [Trưởng thành] "
        f"[{context.get('label', 'Trưởng thành')}] "
        "Quá thời gian polling tối đa 3 phút."
    )
    poller.finish(context, "failed", "Quá thời gian polling tối đa 3 phút")
    return False


def run(worker, account, device, rects, log) -> bool:
    """Chỉ click ô khi category đã có poller tương ứng."""
    pending = list(rects)
    context = {
        "worker": worker,
        "account": account,
        "device": device,
        "log": log,
    }

    while pending:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi xử lý Trưởng Thành.")
            return False

        category, rect, row, column = pending[0]
        label = _LABELS.get(category, category)
        context["label"] = label
        poller = _create_poller(category, context)
        if poller is None:
            pending.pop(0)
            continue

        top, left, right, bottom = rect
        x = round((left + right) / 2)
        y = round((top + bottom) / 2)
        try:
            device.shell(f"input tap {x} {y}")
            log(
                f"[{account.display_name}] [Trưởng thành] [Ô {row}-{column}] "
                f"Click trung điểm ({x}, {y}) [{label}]."
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] [Trưởng thành] [Ô {row}-{column}] "
                f"Không click được [{label}]: {exc}"
            )
            return False

        # Xóa ô khỏi danh sách ngay sau khi đã click trung điểm ô.
        pending.pop(0)

        if not _run_poller(poller, context):
            return False

    log(f"[{account.display_name}] [Trưởng thành] Đã xử lý hết danh sách ô.")
    return True
