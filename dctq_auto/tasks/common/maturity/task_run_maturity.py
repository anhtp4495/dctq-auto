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
}


def _create_poller(category, context):
    """Tạo poller theo category; category chưa hỗ trợ sẽ được bỏ qua."""
    return create_poller(category, context)


def _handle_lord_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Chúa công."""
    chua_cong_found = observation.get("chua_cong")
    if not chua_cong_found:
        return False

    if chua_cong_found.get("chua_chon_chien_ky") is not None:
        found = chua_cong_found["chua_chon_chien_ky"]
        label = "Chưa chọn Chiến kỳ"
    elif chua_cong_found.get("giuong_co") is not None:
        found = chua_cong_found["giuong_co"]
        label = "Giương cờ"
    elif chua_cong_found.get("thoat") is not None:
        found = chua_cong_found["thoat"]
        label = "Thoát màn hình Chúa công"
        poller.waiting_for_main = True
    else:
        return False

    x, y = click_match(context["device"], found)
    context["log"](
        f"[{context['account'].display_name}] [Trưởng thành] [Chúa công] "
        f"Click {label} tại ({x}, {y})."
    )
    return True


def _handle_treasure_observation(observation, poller, context) -> bool:
    """Xử lý trạng thái quan sát được trong luồng Thần binh."""
    than_binh_found = observation.get("than_binh")
    if not than_binh_found:
        return False

    actions = (
        ("loi_vao", "Lối vào Thần binh"),
        ("mien_phi", "Miễn phí"),
        ("an_cho_trong_de_thoat", "Ấn chỗ trống để thoát"),
        ("thoat", "Thoát màn hình Thần binh"),
    )
    for key, label in actions:
        found = than_binh_found.get(key)
        if found is None:
            continue

        x, y = click_match(context["device"], found)
        context["log"](
            f"[{context['account'].display_name}] [Trưởng thành] [Thần binh] "
            f"Click {label} tại ({x}, {y})."
        )
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
                return True
            continue

        if observation.get("chua_cong") is not None:
            _handle_lord_observation(observation, poller, context)
        elif observation.get("than_binh") is not None:
            _handle_treasure_observation(observation, poller, context)

    log(
        f"[{account.display_name}] [Trưởng thành] "
        f"[{context.get('label', 'Trưởng thành')}] "
        "Quá thời gian polling tối đa 3 phút."
    )
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
