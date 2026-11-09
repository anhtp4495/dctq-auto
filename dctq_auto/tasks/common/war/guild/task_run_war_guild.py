"""Nhận thưởng Đoàn Chiến bằng Template Matching, không sử dụng OCR."""

import time

from dctq_auto.config.constants import (
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
)
from dctq_auto.tasks.common.battle.battle_utils import click_match, match, screen_bgr
from dctq_auto.vision.template_store import get_templates
from dctq_auto.vision.template_report import report_template_match


_MAX_TRIES = 3
_POLL_INTERVAL = 1.0
_TEMPLATES = (
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_CHUA_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_NHAN_THUONG,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_AN_CHO_TRONG_DE_THOAT,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET,
    _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET,
)


def run(worker, account, device, log, current_try=1) -> bool:
    """Nhận thưởng Đoàn Chiến nếu còn; trạng thái đã nhận được xem là hoàn tất."""

    if current_try == 1:
        log(f"[{account.display_name}] Bắt đầu kiểm tra trạng thái thưởng Đoàn Chiến.")

    if current_try > _MAX_TRIES:
        log(
            f"[{account.display_name}] Không xác nhận được trạng thái đã nhận thưởng "
            f"Đoàn Chiến sau {_MAX_TRIES} lần; giữ nguyên trạng thái thất bại."
        )
        return False

    if not worker._wait_if_paused():
        log(f"[{account.display_name}] Đã dừng khi đang nhận thưởng Đoàn Chiến.")
        return False

    templates = get_templates(_TEMPLATES)
    screen = screen_bgr(device)

    for template_name in _TEMPLATES:
        template = templates.get(template_name)
        if template is None:
            log(
                f"[{account.display_name}] Không tải được template "
                f"{template_name}; bỏ qua."
            )
            continue

        match_template = match(screen, template, account=account, log=log)
        if match_template is None:
            continue

        report_template_match(
            log,
            context=f"[{account.display_name}]",
            template=template,
            match=match_template,
        )

        if template_name == _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DA_NHAN_THUONG:
            log(f"[{account.display_name}] Đã nhận thưởng Đoàn Chiến.")
            return True

        if template_name == _TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_TONG_KET:
            log(f"[{account.display_name}] Đang ở bảng tổng kết Đoàn Chiến; tìm nút đóng.")
            close_template = templates.get(_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET)
            if close_template is None:
                log(
                    f"[{account.display_name}] Không tải được template "
                    f"{_TEMPLATE_CHIEN_TRANH_DOAN_CHIEN_DONG_TONG_KET}; bỏ qua."
                )
                continue

            close_match = match(screen, close_template, account=account, log=log)
            if close_match is None:
                continue
            match_template = close_match

        x, y = click_match(device, match_template)
        log(
            f"[{account.display_name}] Click trung điểm [{template_name}] "
            f"tại ({x}, {y})."
        )
        time.sleep(_POLL_INTERVAL)
        return run(
            worker,
            account,
            device,
            log,
            current_try=current_try + 1,
        )

    log(
        f"[{account.display_name}] Chưa nhận diện được trạng thái thưởng Đoàn Chiến "
        f"(lần {current_try}/{_MAX_TRIES}); thử lại."
    )
    time.sleep(_POLL_INTERVAL)
    return run(
        worker,
        account,
        device,
        log,
        current_try=current_try + 1,
    )
