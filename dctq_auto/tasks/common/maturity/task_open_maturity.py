"""Mở giao diện Trưởng Thành và quét các ô chưa nhận."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH,
    _TEMPLATE_MAIN_LOI_VAO_TUONG_AN,
    _TEMPLATE_MAIN_TRUONG_THANH,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, screen_bgr
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_MAX_GRID_ROWS = 3
_MAX_GRID_COLUMNS = 4
_GRID_CELL_RECT_SIZE = 20
_MAX_OPEN_TRIES = 2
_OPEN_POLL_INTERVAL = 2.0

_OPEN_TEMPLATES = (
    _TEMPLATE_MAIN_LOI_VAO_TUONG_AN,
    _TEMPLATE_MAIN_TRUONG_THANH,
)


def _find_template(screen, template):
    return match_template(
        screen,
        template.image,
        threshold=template.threshold,
        method=template.method,
        search_rect=template.search_rect,
        grayscale=template.grayscale,
    )


def _scan_unclaimed_cells(screen, template, account, log) -> int:
    """Quét đủ 12 ô, ghi log trạng thái và trung điểm của từng ô khớp."""
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
            cell_number = row * _MAX_GRID_COLUMNS + column + 1

            found = match_template(
                screen,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=(cell_top, cell_left, cell_right, cell_bottom),
                grayscale=template.grayscale,
            )
            context = (
                f"[{account.display_name}] [Trưởng thành] "
                f"[Ô {row + 1}-{column + 1}]"
            )
            if found is None:
                log(f"{context}: không khớp.")
                continue

            matched_count += 1
            x = round((cell_left + cell_right) / 2)
            y = round((cell_top + cell_bottom) / 2)
            half_rect = _GRID_CELL_RECT_SIZE // 2
            rect = (y - half_rect, x - half_rect, x + half_rect, y + half_rect)
            report_template_match(
                log,
                context=context,
                template=template,
                match=found,
            )
            log(
                f"{context}: khớp, trung điểm ({x}, {y}), "
                f"rect 20x20 {rect}."
            )

    log(
        f"[{account.display_name}] [Trưởng thành] "
        f"Tìm thấy {matched_count}/{_MAX_GRID_ROWS * _MAX_GRID_COLUMNS} ô chưa nhận."
    )
    return matched_count


def run(worker, account, device, ocr_client, log) -> bool:
    """Nhận diện màn hình Trưởng Thành, mở nếu cần và quét 12 ô."""
    log(f"[{account.display_name}] Bắt đầu mở màn hình Trưởng Thành.")
    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi mở màn hình Trưởng Thành.")
        return False

    templates = get_templates(_OPEN_TEMPLATES)
    maturity_entry = templates.get(_TEMPLATE_MAIN_LOI_VAO_TUONG_AN)
    main_entry = templates.get(_TEMPLATE_MAIN_TRUONG_THANH)

    if maturity_entry is None:
        log(f"[{account.display_name}] Không tải được template lối vào Tướng Ấn.")
        return False
    if main_entry is None:
        log(f"[{account.display_name}] Không tải được template lối vào Trưởng Thành.")
        return False
    for attempt in range(_MAX_OPEN_TRIES):
        if not worker._wait_if_paused():
            log(f"[{account.display_name}] Đã dừng khi mở màn hình Trưởng Thành.")
            return False

        try:
            screen = screen_bgr(device)
        except Exception as exc:
            log(f"[{account.display_name}] Không chụp được màn hình: {exc}")
            return False

        try:
            maturity_match = _find_template(screen, maturity_entry)
        except Exception as exc:
            log(f"[{account.display_name}] Lỗi nhận diện lối vào Tướng Ấn: {exc}")
            return False

        if maturity_match is not None:
            log(
                f"[{account.display_name}] Đã xác định Trưởng Thành đang mở "
                f"(lần kiểm tra {attempt + 1}/{_MAX_OPEN_TRIES})."
            )
            unclaimed_templates = get_templates(
                (_TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH,)
            )
            unclaimed_template = unclaimed_templates.get(
                _TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH
            )
            if unclaimed_template is None:
                log(
                    f"[{account.display_name}] "
                    "Không tải được template ô chưa nhận Trưởng Thành."
                )
                return False
            try:
                _scan_unclaimed_cells(
                    screen, unclaimed_template, account, log
                )
            except Exception as exc:
                log(f"[{account.display_name}] Lỗi quét 12 ô Trưởng Thành: {exc}")
                return False
            return True

        log(
            f"[{account.display_name}] Không tìm thấy lối vào Tướng Ấn "
            f"(lần kiểm tra {attempt + 1}/{_MAX_OPEN_TRIES})."
        )
        if attempt == _MAX_OPEN_TRIES - 1:
            break

        try:
            main_match = _find_template(screen, main_entry)
        except Exception as exc:
            log(f"[{account.display_name}] Lỗi nhận diện lối vào Trưởng Thành: {exc}")
            return False

        if main_match is None:
            log(f"[{account.display_name}] Không tìm thấy lối vào Trưởng Thành để click.")
            return False

        x, y = click_match(device, main_match)
        log(f"[{account.display_name}] Click lối vào Trưởng Thành tại ({x}, {y}).")
        time.sleep(_OPEN_POLL_INTERVAL)

    log(
        f"[{account.display_name}] Không mở được màn hình Trưởng Thành "
        f"sau {_MAX_OPEN_TRIES} lần kiểm tra; kết thúc task."
    )
    return False
