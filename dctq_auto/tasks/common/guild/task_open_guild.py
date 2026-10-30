"""Mở và xác minh màn hình [Quân đoàn]."""

import time
from pathlib import Path

import cv2
import numpy as np

from dctq_auto.config.constants import _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_OPEN_CHAT_DELAY = 0.8
_ENTER_GUILD_DELAY = 2.0
_MAX_VERIFY_ATTEMPTS = 5


def _is_guild_screen(worker, account, device, log) -> bool:
    """Xác nhận đã vào màn hình chính Quân đoàn bằng template."""
    template = get_templates((_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,)).get(
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH
    )
    if template is None:
        log(
            f"[{account.username}] Không tải được template "
            f"{_TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH} để xác minh Quân đoàn."
        )
        return False

    try:
        screenshot = device.screenshot()
        screen_bgr = cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
        match = match_template(
            screen_bgr,
            template.image,
            threshold=template.threshold,
            method=template.method,
            search_rect=template.search_rect,
        )
    except Exception as exc:
        log(f"[{account.username}] Lỗi khi xác minh màn hình Quân đoàn: {exc}")
        return False

    if match is None:
        return False

    report_template_match(
        log,
        context=f"[{account.username}]",
        template=template,
        match=match,
    )
    return True


def run(worker, account, device, ocr_client, log, screenshot=None) -> bool:
    """Mở Quân đoàn từ nút chat, chọn 'Vào quân đoàn' và xác minh kết quả.

    Screenshot truyền từ task gọi bên ngoài không được dùng vì các thao tác
    mở chat làm thay đổi màn hình; mỗi lần xác minh đều chụp ảnh mới.
    """
    regions_path = Path(__file__).resolve().parents[1] / "regions.json"

    if not worker._wait_if_paused():
        log(f"[{account.username}] Đã dừng trước khi mở màn hình [Quân đoàn].")
        return False

    if screenshot is not None:
        log(
            f"[{account.username}] Bỏ qua screenshot cũ khi mở Quân đoàn; "
            "sẽ chụp ảnh mới sau mỗi thao tác."
        )

    # Tránh bấm mở chat lần nữa nếu hiện tại đã ở trong màn hình Quân đoàn.
    if _is_guild_screen(worker, account, device, log):
        log(f"[{account.username}] Đã ở sẵn màn hình [Quân đoàn].")
        return True

    log(
        f"[{account.username}] Vào Quân đoàn — BƯỚC 1: "
        "click open_chat_quan_doan theo tọa độ trong regions.json."
    )
    try:
        x, y = ocr_client.tap_ocr_target(
            "open_chat_quan_doan", regions_path=regions_path
        )
        log(
            f"[{account.username}] Đã click open_chat_quan_doan tại ({x}, {y}); "
            "chờ giao diện chat tải."
        )
    except Exception as exc:
        log(f"[{account.username}] Không mở được chat Quân đoàn: {exc}")
        return False

    time.sleep(_OPEN_CHAT_DELAY)

    if not worker._wait_if_paused():
        log(f"[{account.username}] Đã dừng trước khi chọn Vào quân đoàn.")
        return False

    # Nút 'Vào quân đoàn' nằm trong nhóm tọa độ login của regions.json.
    # OCR toàn màn hình chỉ dùng để xác nhận đúng trạng thái trước khi click.
    try:
        screen_text = worker._normalize_screen_text(worker._screen_text(device))
    except Exception as exc:
        log(f"[{account.username}] Không đọc được trạng thái chat Quân đoàn: {exc}")
        return False

    if "vao quan doan" not in screen_text:
        log(
            f"[{account.username}] Không thấy OCR 'vao_quan_doan' sau khi mở chat; "
            f"không click nút vào Quân đoàn. OCR: {screen_text[:180] or '(trống)'}"
        )
        return False

    log(
        f"[{account.username}] Vào Quân đoàn — BƯỚC 2: "
        "OCR xác nhận 'vao_quan_doan', click nút vào Quân đoàn."
    )
    try:
        x, y = ocr_client.tap_ocr_target(
            "vao_quan_doan",
            regions_path=regions_path,
        )
        log(f"[{account.username}] Đã click vao_quan_doan tại ({x}, {y}).")
    except Exception as exc:
        log(f"[{account.username}] Không click được nút Vào quân đoàn: {exc}")
        return False

    time.sleep(_ENTER_GUILD_DELAY)

    for attempt in range(1, _MAX_VERIFY_ATTEMPTS + 1):
        if not worker._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi xác minh màn hình Quân đoàn.")
            return False

        if _is_guild_screen(worker, account, device, log):
            log(
                f"[{account.username}] Đã xác nhận vào màn hình [Quân đoàn] "
                f"(lần kiểm tra {attempt}/{_MAX_VERIFY_ATTEMPTS})."
            )
            return True

        if attempt < _MAX_VERIFY_ATTEMPTS:
            log(
                f"[{account.username}] Chưa nhận diện được màn hình Quân đoàn "
                f"(lần {attempt}/{_MAX_VERIFY_ATTEMPTS}); chờ 1 giây rồi kiểm tra lại."
            )
            time.sleep(1)

    log(
        f"[{account.username}] Không xác nhận được màn hình [Quân đoàn] "
        f"sau {_MAX_VERIFY_ATTEMPTS} lần kiểm tra."
    )
    return False
