"""Xử lý các ô Trưởng Thành đã được phân loại."""

from dctq_auto.tasks.common.battle.battle_utils import click_match
from dctq_auto.tasks.common.maturity.polling import create_poller


_MAX_POLL_TRIES = 5

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


def _run_poller(poller, context) -> bool:
    """Polling và xử lý observation của category."""
    account = context["account"]
    log = context["log"]

    for attempt in range(1, _MAX_POLL_TRIES + 1):
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

            log(
                f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                f"Chưa thấy màn hình Trưởng Thành "
                f"(lần {attempt}/{_MAX_POLL_TRIES})."
            )
            continue

        # Ưu tiên xử lý theo đúng thứ tự của luồng Chúa công.
        actions = (
            ("chua_chon_chien_ky", "Chưa chọn Chiến kỳ"),
            ("giuong_co", "Giương cờ"),
            ("thoat", "Thoát màn hình Chúa công"),
        )
        for key, label in actions:
            found = observation.get(key)
            if found is None:
                continue

            x, y = click_match(context["device"], found)
            log(
                f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                f"Click {label} tại ({x}, {y})."
            )
            if key == "thoat":
                poller.waiting_for_main = True
            break
        else:
            log(
                f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                f"Chưa khớp trạng thái (lần {attempt}/{_MAX_POLL_TRIES})."
            )

    log(
        f"[{account.display_name}] [Trưởng thành] [Chúa công] "
        f"Không hoàn tất sau {_MAX_POLL_TRIES} lần polling."
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
