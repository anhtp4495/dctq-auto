"""Mở giao diện Trưởng Thành và quét các ô chưa nhận."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH,
    _TEMPLATE_MAIN_TRUONG_THANH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, screen_bgr
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_GRID_ROWS = 3
_MAX_GRID_COLUMNS = 4
_POLL_INTERVAL = 1.5
_TEMPLATES = (
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH,
)


def _scan_unclaimed_cells(screen, template, account, log) -> int:
    """Quét từng ô trong lưới 3x4 và ghi trung điểm các ô có trạng thái chưa nhận."""
    top, left, right, bottom = template.search_rect
    width = right - left
    height = bottom - top
    matched_count = 0

    for row in range(_MAX_GRID_ROWS):
        cell_top = top + row * height // _MAX_GRID_ROWS
        cell_bottom = top + (row + 1) * height // _MAX_GRID_ROWS
        for column in range(_MAX_GRID_COLUMNS):
            cell_left = left + column * width // _MAX_GRID_COLUMNS
            cell_right = left + (column + 1) * width // _MAX_GRID_COLUMNS
            found = match_template(
                screen,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=(cell_top, cell_left, cell_right, cell_bottom),
                grayscale=template.grayscale,
            )
            if found is None:
                continue

            matched_count += 1
            x = round((found.left + found.right) / 2)
            y = round((found.top + found.bottom) / 2)
            report_template_match(
                log,
                context=f"[{account.display_name}] [Trưởng thành] [Ô {row + 1}-{column + 1}]",
                template=template,
                match=found,
            )
            log(
                f"[{account.display_name}] [Trưởng thành] "
                f"Ô hàng {row + 1}, cột {column + 1}: trung điểm ({x}, {y})."
            )

    log(
        f"[{account.display_name}] [Trưởng thành] "
        f"Tìm thấy {matched_count}/{_MAX_GRID_ROWS * _MAX_GRID_COLUMNS} ô chưa nhận."
    )
    return matched_count


def run(worker, account, device, ocr_client, log) -> bool:
    """Click lối vào Trưởng Thành, sau đó quét 12 ô chưa nhận."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình Trưởng Thành.")
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi mở màn hình Trưởng Thành.")
        return False

    templates = get_templates(_TEMPLATES)
    entry_template = templates.get(_TEMPLATE_MAIN_TRUONG_THANH)
    unclaimed_template = templates.get(_TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH)
    if entry_template is None or unclaimed_template is None:
        log(f"[{account.display_name}] Không tải được template Trưởng Thành.")
        return False

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình chính: {exc}")
        return False

    try:
        found = match_template(
            screen,
            entry_template.image,
            threshold=entry_template.threshold,
            method=entry_template.method,
            search_rect=entry_template.search_rect,
            grayscale=entry_template.grayscale,
        )
    except Exception as exc:
        log(f"[{account.display_name}] Lỗi matching lối vào Trưởng Thành: {exc}")
        return False

    if found is None:
        log(f"[{account.display_name}] Không tìm thấy lối vào Trưởng Thành.")
        return False

    x, y = click_match(device, found)
    log(f"[{account.display_name}] Click lối vào Trưởng Thành tại ({x}, {y}).")
    time.sleep(_POLL_INTERVAL)

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng trước khi quét Trưởng Thành.")
        return False

    try:
        screen = screen_bgr(device)
    except Exception as exc:
        log(f"[{account.display_name}] Không chụp được màn hình Trưởng Thành: {exc}")
        return False

    try:
        _scan_unclaimed_cells(screen, unclaimed_template, account, log)
    except Exception as exc:
        log(f"[{account.display_name}] Lỗi quét các ô chưa nhận Trưởng Thành: {exc}")
        return False
    return True
