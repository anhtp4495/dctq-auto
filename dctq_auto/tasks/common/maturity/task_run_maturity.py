"""Xử lý các ô Trưởng Thành đã được phân loại."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MATURITY_CHUA_CONG_CHUA_CHON_CHIEN_KY,
    _TEMPLATE_MATURITY_CHUA_CONG_GIUONG_CO,
    _TEMPLATE_MATURITY_CHUA_CONG_THOAT,
    _TEMPLATE_MAIN_TRUONG_THANH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, screen_bgr
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_store import get_templates


_POLL_INTERVAL = 1.0
_MAX_POLL_TRIES = 5

_CHUA_CONG_TEMPLATES = (
    _TEMPLATE_MATURITY_CHUA_CONG_CHUA_CHON_CHIEN_KY,
    _TEMPLATE_MATURITY_CHUA_CONG_GIUONG_CO,
    _TEMPLATE_MATURITY_CHUA_CONG_THOAT,
    _TEMPLATE_MAIN_TRUONG_THANH,
)

_LABELS = {
    "chua_cong": "Chúa công",
    "ve_tuong": "Vệ tướng",
    "than_binh": "Thần binh",
    "chien_hon": "Chiến hồn",
    "tuong_an": "Tướng ấn",
}


def _find_template(screen, template):
    return match_template(
        screen,
        template.image,
        threshold=template.threshold,
        method=template.method,
        search_rect=template.search_rect,
        grayscale=template.grayscale,
    )


def _run_chua_cong(worker, account, device, log) -> bool:
    """Thực hiện các thao tác Chiến kỳ, Giương cờ và thoát Chúa công."""
    templates = get_templates(_CHUA_CONG_TEMPLATES)
    missing = [name for name in _CHUA_CONG_TEMPLATES if name not in templates]
    if missing:
        log(
            f"[{account.display_name}] [Trưởng thành] [Chúa công] "
            f"Thiếu template: {', '.join(missing)}."
        )
        return False

    exit_clicked = False
    for attempt in range(_MAX_POLL_TRIES):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi xử lý Chúa công.")
            return False

        try:
            screen = screen_bgr(device)
            if exit_clicked:
                main_template = templates[_TEMPLATE_MAIN_TRUONG_THANH]
                if _find_template(screen, main_template) is not None:
                    log(
                        f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                        "Đã xác nhận quay về màn hình Trưởng Thành."
                    )
                    return True
                log(
                    f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                    f"Đang chờ màn hình Trưởng Thành "
                    f"(lần {attempt + 1}/{_MAX_POLL_TRIES})."
                )
                time.sleep(_POLL_INTERVAL)
                continue

            # Thứ tự ưu tiên theo luồng thao tác đã thống nhất.
            for template_name in _CHUA_CONG_TEMPLATES[:-2]:
                template = templates[template_name]
                found = _find_template(screen, template)
                if found is None:
                    continue

                x, y = click_match(device, found)
                log(
                    f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                    f"Click {template_name.rsplit('/', 1)[-1]} tại ({x}, {y})."
                )
                break
            else:
                exit_template = templates[_TEMPLATE_MATURITY_CHUA_CONG_THOAT]
                found = _find_template(screen, exit_template)
                if found is not None:
                    x, y = click_match(device, found)
                    exit_clicked = True
                    log(
                        f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                        f"Click thoát tại ({x}, {y}); chờ xác nhận màn hình Trưởng Thành."
                    )
                else:
                    log(
                        f"[{account.display_name}] [Trưởng thành] [Chúa công] "
                        f"Chưa khớp trạng thái (lần {attempt + 1}/{_MAX_POLL_TRIES})."
                    )
        except Exception as exc:
            log(f"[{account.display_name}] Lỗi xử lý Chúa công: {exc}")
            return False

        time.sleep(_POLL_INTERVAL)

    log(
        f"[{account.display_name}] [Trưởng thành] [Chúa công] "
        f"Không hoàn tất sau {_MAX_POLL_TRIES} lần polling."
    )
    return False


def run(worker, account, device, rects, log) -> bool:
    """Click trung điểm các ô thuộc 5 nhóm được hỗ trợ."""
    pending = list(rects)

    while pending:
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi xử lý Trưởng Thành.")
            return False

        category, rect, row, column = pending[0]
        label = _LABELS.get(category)
        if label is None:
            log(
                f"[{account.display_name}] [Trưởng thành] [Ô {row}-{column}] "
                f"Không hỗ trợ loại {category}; bỏ qua."
            )
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

        if category == "chua_cong":
            if not _run_chua_cong(worker, account, device, log):
                return False

    log(f"[{account.display_name}] [Trưởng thành] Đã xử lý hết danh sách ô.")
    return True
