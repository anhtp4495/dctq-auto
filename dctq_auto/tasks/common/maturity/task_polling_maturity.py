"""Polling trạng thái màn hình Trưởng Thành sau khi thoát Chúa công."""

import time

from dctq_auto.config.constants import _TEMPLATE_MAIN_TRUONG_THANH
from dctq_auto.tasks.common.battle.battle_utils import screen_bgr
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_store import get_templates


_MAX_POLL_TRIES = 5
_POLL_INTERVAL = 1.0


def run(worker, account, device, log, current_try=1) -> bool:
    """Chờ màn hình Trưởng Thành xuất hiện sau thao tác thoát."""
    if current_try > _MAX_POLL_TRIES:
        log(
            f"[{account.display_name}] [Trưởng thành] "
            f"Không xác nhận được màn hình Trưởng Thành sau {_MAX_POLL_TRIES} lần polling."
        )
        return False

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi polling màn hình Trưởng Thành.")
        return False

    templates = get_templates((_TEMPLATE_MAIN_TRUONG_THANH,))
    template = templates.get(_TEMPLATE_MAIN_TRUONG_THANH)
    if template is None:
        log(
            f"[{account.display_name}] [Trưởng thành] "
            "Không tải được template màn hình Trưởng Thành."
        )
        return False

    try:
        screen = screen_bgr(device)
        found = match_template(
            screen,
            template.image,
            threshold=template.threshold,
            method=template.method,
            search_rect=template.search_rect,
            grayscale=template.grayscale,
        )
    except Exception as exc:
        log(
            f"[{account.display_name}] [Trưởng thành] "
            f"Lỗi polling màn hình (lần {current_try}/{_MAX_POLL_TRIES}): {exc}"
        )
        return False

    if found is not None:
        log(
            f"[{account.display_name}] [Trưởng thành] "
            "Đã xác nhận quay về màn hình Trưởng Thành."
        )
        return True

    log(
        f"[{account.display_name}] [Trưởng thành] "
        f"Chưa thấy màn hình Trưởng Thành "
        f"(lần {current_try}/{_MAX_POLL_TRIES})."
    )
    if current_try < _MAX_POLL_TRIES:
        time.sleep(_POLL_INTERVAL)
        return run(worker, account, device, log, current_try + 1)

    return False
