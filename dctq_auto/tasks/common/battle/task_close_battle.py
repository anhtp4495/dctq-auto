"""Đóng quy trình Giao Tranh bằng thao tác Hồi thành."""

import time

from dctq_auto.config.constants import _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import (
    click_match as _click_match,
    match as _match,
    screen_bgr as _screen_bgr,
)


def run(self, account, device, ocr_client, log) -> bool:
    """Chờ template Hồi thành và click trung điểm để rời Giao Tranh."""
    templates = get_templates((_TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,))
    max_attempts = 180
    for attempt in range(1, max_attempts + 1):
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng trước khi Hồi thành.")
            return False
        try:
            screen = _screen_bgr(device)
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình để Hồi thành: {exc}")
            return False
        match = _match(
            screen,
            templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH),
            account=account, log=log,
        )
        if match is not None:
            x, y = _click_match(device, match)
            log(f"[{account.username}] Đã click Hồi thành tại ({x}, {y}).")
            time.sleep(1)
            return True
        if attempt % 10 == 0:
            log(
                f"[{account.username}] Đang chờ Hồi thành "
                f"(lần {attempt}/{max_attempts})."
            )
        time.sleep(1)

    log(f"[{account.username}] Không phát hiện Hồi thành sau {max_attempts} giây.")
    return False

