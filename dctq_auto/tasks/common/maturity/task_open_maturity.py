"""Mở giao diện Trưởng Thành và quét các ô chưa nhận."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_MAIN_CHUA_NHAN_TRUONG_THANH,
    _TEMPLATE_MAIN_LOI_VAO_TUONG_AN,
    _TEMPLATE_MAIN_TRUONG_THANH,
    _TEMPLATE_MAIN_TRUONG_THANH_BAO_VAT,
    _TEMPLATE_MAIN_TRUONG_THANH_TUONG_AN,
    _TEMPLATE_MAIN_TRUONG_THANH_CHUA_CONG,
    _TEMPLATE_MAIN_TRUONG_THANH_VE_TUONG,
    _TEMPLATE_MAIN_TRUONG_THANH_THAN_BINH,
    _TEMPLATE_MAIN_TRUONG_THANH_CHIEN_HON,
    _TEMPLATE_MAIN_TRUONG_THANH_THAN_TUONG,
    _TEMPLATE_MAIN_TRUONG_THANH_TRAI_NGUA,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, screen_bgr
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_store import get_screen_image, get_templates


_MAX_GRID_ROWS = 3
_MAX_GRID_COLUMNS = 4
_GRID_CELL_RECT_SIZE = 60
_MAX_OPEN_TRIES = 2
_OPEN_POLL_INTERVAL = 2.0

_OPEN_TEMPLATES = (
    _TEMPLATE_MAIN_LOI_VAO_TUONG_AN,
    _TEMPLATE_MAIN_TRUONG_THANH,
)

_CLASSIFICATION_TEMPLATES = (
    _TEMPLATE_MAIN_TRUONG_THANH_BAO_VAT,
    _TEMPLATE_MAIN_TRUONG_THANH_TUONG_AN,
    _TEMPLATE_MAIN_TRUONG_THANH_CHUA_CONG,
    _TEMPLATE_MAIN_TRUONG_THANH_VE_TUONG,
    _TEMPLATE_MAIN_TRUONG_THANH_THAN_BINH,
    _TEMPLATE_MAIN_TRUONG_THANH_CHIEN_HON,
    _TEMPLATE_MAIN_TRUONG_THANH_THAN_TUONG,
    _TEMPLATE_MAIN_TRUONG_THANH_TRAI_NGUA,
)

_CLASSIFICATION_LABELS = {
    _TEMPLATE_MAIN_TRUONG_THANH_BAO_VAT: "Bảo vật",
    _TEMPLATE_MAIN_TRUONG_THANH_TUONG_AN: "Tướng ấn",
    _TEMPLATE_MAIN_TRUONG_THANH_CHUA_CONG: "Chúa công",
    _TEMPLATE_MAIN_TRUONG_THANH_VE_TUONG: "Vệ tướng",
    _TEMPLATE_MAIN_TRUONG_THANH_THAN_BINH: "Thần binh",
    _TEMPLATE_MAIN_TRUONG_THANH_CHIEN_HON: "Chiến hồn",
    _TEMPLATE_MAIN_TRUONG_THANH_THAN_TUONG: "Thần tượng",
    _TEMPLATE_MAIN_TRUONG_THANH_TRAI_NGUA: "Trại ngựa",
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


def _classify_cell(cell_image, source_image, templates):
    """Phân loại ảnh ô bằng cách tìm ảnh ô trong từng vùng rect của ảnh nguồn."""
    best_match = None
    best_template = None

    for template_name in _CLASSIFICATION_TEMPLATES:
        template = templates.get(template_name)
        if template is None:
            continue
        found = match_template(
            source_image,
            cell_image,
            threshold=template.threshold,
            method=template.method,
            search_rect=template.rect,
            grayscale=template.grayscale,
        )
        if found is not None and (
            best_match is None or found.score > best_match.score
        ):
            best_match = found
            best_template = template

    return best_template, best_match


def _scan_unclaimed_cells(
    screen, template, source_image, classification_templates, account, log
) -> int:
    """Quét 12 ô chưa nhận và phân loại từng ô đã khớp."""
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
            context = (
                f"[{account.display_name}] [Trưởng thành] "
                f"[Ô {row + 1}-{column + 1}]"
            )

            found = match_template(
                screen,
                template.image,
                threshold=template.threshold,
                method=template.method,
                search_rect=(cell_top, cell_left, cell_right, cell_bottom),
                grayscale=template.grayscale,
            )
            if found is None:
                log(f"{context}: không khớp.")
                continue

            matched_count += 1
            x = round((cell_left + cell_right) / 2)
            y = round((cell_top + cell_bottom) / 2)
            half_rect = _GRID_CELL_RECT_SIZE // 2
            rect = (y - half_rect, x - half_rect, x + half_rect, y + half_rect)
            cell_image = screen[rect[0]:rect[3], rect[1]:rect[2]]
            if cell_image.size == 0:
                log(f"{context}: khớp ô chưa nhận nhưng ảnh crop rỗng (rect={rect}).")
                continue

            matched_template, classification_match = _classify_cell(
                cell_image, source_image, classification_templates
            )
            if matched_template is None:
                log(
                    f"{context}: khớp ô chưa nhận nhưng chưa phân loại "
                    f"(rect={rect})."
                )
                continue

            label = _CLASSIFICATION_LABELS[matched_template.id]
            log(
                f"{context}: khớp "
                f"(score={classification_match.score:.3f}, "
                f"threshold={matched_template.threshold:.2f}, rect={rect}) "
                f"[{label}]"
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
            classification_templates = get_templates(_CLASSIFICATION_TEMPLATES)
            source_image = get_screen_image("main")
            if source_image is None:
                log(f"[{account.display_name}] Không tải được ảnh nguồn phân loại Trưởng thành.")
                return False
            missing_templates = [
                name for name in _CLASSIFICATION_TEMPLATES
                if name not in classification_templates
            ]
            if missing_templates:
                log(
                    f"[{account.display_name}] Thiếu template phân loại Trưởng thành: "
                    f"{', '.join(missing_templates)}."
                )
                return False
            try:
                _scan_unclaimed_cells(
                    screen,
                    unclaimed_template,
                    source_image,
                    classification_templates,
                    account,
                    log,
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
