"""Điều phối quy trình Giao Tranh bằng Template Matching và tọa độ cấu hình."""

from __future__ import annotations

import time

import cv2
import numpy as np

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _STEP_QUAN_SU_GIAO_TRANH,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
)
from dctq_auto.vision.template_matching import match_template
from dctq_auto.vision.template_report import report_template_match
from dctq_auto.vision.template_store import get_templates


_TASK_LABELS = {
    "task_open_battle": "Mở màn hình Giao Tranh",
    "task_use_bazhen": "Sử dụng Canh Bát Trận",
    "task_find_battle_opponent": "Tìm đối thủ Giao Tranh",
    "xuat_chien": "Xuất chiến",
    "task_start_battle": "Bắt đầu trận Giao Tranh",
    "task_end_battle": "Kết thúc trận Giao Tranh",
}

_OPEN_TEMPLATES = (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO,
    _TEMPLATE_MAIN_QUAN_SU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN,
)
_BATTLE_TEMPLATES = (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
)


def _screen_bgr(device) -> np.ndarray:
    """Chụp màn hình và chuyển ảnh RGB từ ADB sang BGR cho OpenCV."""
    return cv2.cvtColor(np.asarray(device.screenshot()), cv2.COLOR_RGB2BGR)


def _match(screen_bgr, template, *, account, log):
    if template is None:
        return None
    try:
        result = match_template(
            screen_bgr,
            template.image,
            threshold=template.threshold,
            method=template.method,
            search_rect=template.search_rect,
            grayscale=template.grayscale,
        )
    except (ValueError, cv2.error) as exc:
        log(f"[{account.username}] Lỗi matching template {template.id}: {exc}")
        return None
    if result is not None:
        report_template_match(
            log,
            context=f"[{account.username}]",
            template=template,
            match=result,
        )
    return result


def _click_match(device, match) -> tuple[int, int]:
    x = round((match.left + match.right) / 2)
    y = round((match.top + match.bottom) / 2)
    device.shell(f"input tap {x} {y}")
    return x, y


def _mode(config) -> str:
    if config.get("giao_tranh_nhanh_1_co"):
        return "fast"
    if config.get("ba_co"):
        return "normal"
    if config.get("task_battle_time_mode"):
        return "time_limit"
    return "normal"


def pre_battle(config, steps, log) -> bool:
    """Kiểm tra cấu hình Giao Tranh trước khi bắt đầu."""
    if _STEP_QUAN_SU_GIAO_TRANH not in steps:
        log("Giao Tranh: thiếu step quan_su_giao_tranh trong danh sách steps.")
        return False

    try:
        battle_count = int(config.get("task_open_battle_count", 1))
        if battle_count < 1:
            raise ValueError("Số trận phải lớn hơn hoặc bằng 1.")

        selected_modes = sum(
            bool(config.get(key))
            for key in ("giao_tranh_nhanh_1_co", "ba_co", "task_battle_time_mode")
        )
        if selected_modes > 1:
            raise ValueError("Chỉ được chọn một chế độ chiến đấu Giao Tranh.")

        if config.get("task_battle_time_mode"):
            seconds = int(
                config.get("task_battle_time_limit")
                or config.get("thoi_gian_giao_tranh")
                or 0
            )
            if seconds < 1:
                raise ValueError("Thời gian tối đa Giao Tranh phải lớn hơn 0 giây.")
    except (TypeError, ValueError) as exc:
        log(f"Giao Tranh: cấu hình không hợp lệ: {exc}")
        return False

    log(
        f"Giao Tranh: cấu hình hợp lệ — {battle_count} trận, "
        f"chế độ {_mode(config)}."
    )
    return True


def post_battle(log) -> None:
    """Điểm hậu xử lý; hiện tại chỉ ghi log."""
    log("Giao Tranh: hoàn tất quy trình, chưa có xử lý hậu trận.")


def task_open_battle(self, account, device, ocr_client, log, screenshot=None) -> bool:
    """Điều hướng vào Giao Tranh, chọn bộ tọa độ và click Xuất chiến."""
    if not self._wait_if_paused():
        log(f"[{account.username}] Đã dừng trước khi mở Giao Tranh.")
        return False

    log(f"[{account.username}] Bắt đầu mở màn hình Giao Tranh.")
    templates = get_templates(_OPEN_TEMPLATES)
    positions = ButtonPositions()
    max_attempts = 60
    full_open = bool(self._config.get("task_open_battle") or self._config.get("xuat_chien"))

    for attempt in range(1, max_attempts + 1):
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang mở Giao Tranh.")
            return False
        try:
            screen = (
                cv2.cvtColor(np.asarray(screenshot), cv2.COLOR_RGB2BGR)
                if screenshot is not None else _screen_bgr(device)
            )
            screenshot = None
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình Giao Tranh: {exc}")
            return False

        # Bước 1: đang ở màn hình chính Quân Sự thì mở lối vào Giao Tranh.
        entry = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_LOI_VAO),
            account=account, log=log,
        )
        if entry is not None:
            x, y = _click_match(device, entry)
            log(f"[{account.username}] Click lối vào Giao Tranh tại ({x}, {y}).")
            time.sleep(1)
            continue

        # Bước 2: nếu chưa thấy lối vào, mở mục Quân Sự rồi nhận diện lại.
        quan_su = _match(
            screen, templates.get(_TEMPLATE_MAIN_QUAN_SU),
            account=account, log=log,
        )
        if quan_su is not None:
            x, y = _click_match(device, quan_su)
            log(f"[{account.username}] Click Quân Sự tại ({x}, {y}); sẽ tìm lối vào Giao Tranh.")
            time.sleep(1)
            continue

        # Bước 3: chỉ dùng Canh Bát Trận khi người dùng bật tác vụ tương ứng.
        if self._config.get("task_use_bazhen"):
            bazhen = _match(
                screen,
                templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CHUA_SU_DUNG_CANH_BAT_TRAN),
                account=account, log=log,
            )
            if bazhen is not None:
                x, y = _click_match(device, bazhen)
                log(f"[{account.username}] Click sử dụng Canh Bát Trận tại ({x}, {y}).")
                time.sleep(1)
                if not full_open and not self._config.get("task_find_battle_opponent"):
                    return True
                continue

        if not full_open and not self._config.get("task_find_battle_opponent"):
            # Nếu không yêu cầu mở tiếp quy trình, không tự ý tìm đối thủ.
            log(f"[{account.username}] Đã xử lý bước Canh Bát Trận được chọn.")
            return True

        # Bước 4: mở giao diện tìm đối thủ.
        opponent = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_TIM_DOI_THU),
            account=account, log=log,
        )
        if opponent is not None:
            x, y = _click_match(device, opponent)
            log(f"[{account.username}] Click Tìm đối thủ tại ({x}, {y}).")
            time.sleep(1)
            if not full_open:
                return True
            continue

        # Bước 5: xử lý hộp thoại Kim Bài Miễn Chiến.
        immunity = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_BAI_MIEN_CHIEN),
            account=account, log=log,
        )
        if immunity is not None:
            x, y = positions.get(
                "quan_su.giao_tranh", "phat_dong_tan_cong_bo_bai_mien_chien"
            )
            device.shell(f"input tap {x} {y}")
            log(
                f"[{account.username}] Phát hiện Bài Miễn Chiến; "
                f"click phát động giao tranh tại ({x}, {y})."
            )
            time.sleep(1)
            continue

        # Bước 6: Cẩm Nang chỉ là dấu hiệu nhận diện, không cần thao tác.
        cam_nang = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CAM_NANG),
            account=account, log=log,
        )
        if cam_nang is not None:
            log(f"[{account.username}] Đã nhận diện Cẩm Nang; tiếp tục tìm nút Xuất chiến.")

        # Bước 7: nhận diện Chiến Thuật để chọn đúng bộ tọa độ, rồi click Xuất chiến.
        xuat_chien = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_XUAT_CHIEN),
            account=account, log=log,
        )
        if xuat_chien is not None:
            if not full_open:
                log(
                    f"[{account.username}] Đã tới giao diện Xuất chiến; "
                    "dừng tại đây vì chưa chọn tác vụ mở trận."
                )
                return True
            chien_thuat = _match(
                screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT),
                account=account, log=log,
            )
            group = (
                "quan_su.giao_tranh.danh_sach1"
                if chien_thuat is not None
                else "quan_su.giao_tranh.danh_sach2"
            )
            self._battle_hero_position_group = group
            log(
                f"[{account.username}] Chọn bộ tọa độ võ tướng {group} "
                f"({'có' if chien_thuat is not None else 'không có'} Chiến Thuật)."
            )
            x, y = _click_match(device, xuat_chien)
            log(f"[{account.username}] Click Xuất chiến tại ({x}, {y}); chờ vào trận.")
            time.sleep(1)
            return True

        log(
            f"[{account.username}] Mở Giao Tranh — chưa nhận diện được trạng thái "
            f"(lần {attempt}/{max_attempts}); sẽ thử lại."
        )
        time.sleep(1)

    log(f"[{account.username}] Mở Giao Tranh thất bại: quá {max_attempts} lần kiểm tra.")
    return False


def _battle_mode_should_end(
    config, mode, screen, templates, *, account, log, battle_started_at
) -> bool:
    """Kiểm tra điều kiện kết thúc lượt giao tranh; chỉ trả về True/False."""
    if mode == "fast":
        for template_name in (
            _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
            _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
        ):
            match = _match(
                screen, templates.get(template_name), account=account, log=log
            )
            if match is not None:
                log(
                    f"[{account.username}] Chế độ nhanh 1 cờ: đã phát hiện "
                    f"{template_name.rsplit('/', 1)[-1]}."
                )
                return True
        return False

    if mode == "normal":
        return False

    seconds = int(
        config.get("task_battle_time_limit")
        or config.get("thoi_gian_giao_tranh")
        or 15
    )
    if battle_started_at is None:
        return False
    elapsed = time.monotonic() - battle_started_at
    if elapsed >= seconds:
        log(
            f"[{account.username}] Đã vượt thời gian tối đa "
            f"{seconds} giây (thực tế {elapsed:.1f} giây)."
        )
        return True
    return False


def battle_run(self, account, device, ocr_client, log) -> bool:
    """Thả võ tướng, theo dõi trạng thái trận và xử lý chế độ chiến đấu."""
    templates = get_templates(_BATTLE_TEMPLATES)
    group = getattr(self, "_battle_hero_position_group", None)
    if group not in (
        "quan_su.giao_tranh.danh_sach1",
        "quan_su.giao_tranh.danh_sach2",
    ):
        # Nếu bắt đầu từ màn hình trận có sẵn, xác định bộ tọa độ bằng Chiến Thuật.
        strategy_template = get_templates((_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,))
        try:
            screen = _screen_bgr(device)
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình để chọn bộ võ tướng: {exc}")
            return False
        strategy_match = _match(
            screen, strategy_template.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT),
            account=account, log=log,
        )
        group = (
            "quan_su.giao_tranh.danh_sach1"
            if strategy_match is not None
            else "quan_su.giao_tranh.danh_sach2"
        )
        self._battle_hero_position_group = group
        log(f"[{account.username}] Chọn bộ tọa độ võ tướng {group}.")

    positions = ButtonPositions()
    hero_points = [
        positions.get(group, f"vo_tuong_{index}")
        for index in range(1, 6)
    ]
    mode = _mode(self._config)
    target_battles = max(1, int(self._config.get("task_open_battle_count", 1)))
    completed_battles = 0
    hero_deployed = False
    battle_started_at = None
    retreat_requested = False
    awaiting_next_screen = False
    deadline = time.monotonic() + max(180, target_battles * 180)

    log(
        f"[{account.username}] Bắt đầu theo dõi Giao Tranh: "
        f"{target_battles} trận, chế độ {mode}."
    )

    while time.monotonic() < deadline:
        if not self._wait_if_paused():
            log(f"[{account.username}] Đã dừng khi đang chạy Giao Tranh.")
            return False
        try:
            screen = _screen_bgr(device)
        except Exception as exc:
            log(f"[{account.username}] Không chụp được màn hình trận đấu: {exc}")
            return False

        retreat = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI),
            account=account, log=log,
        )
        collect = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN),
            account=account, log=log,
        )
        next_battle = _match(
            screen, templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU),
            account=account, log=log,
        )

        if awaiting_next_screen:
            if next_battle is not None:
                time.sleep(1)
                continue
            awaiting_next_screen = False

        if next_battle is not None:
            completed_battles += 1
            log(
                f"[{account.username}] Phát hiện Trận sau: "
                f"hoàn thành {completed_battles}/{target_battles} trận."
            )
            if completed_battles >= target_battles:
                log(f"[{account.username}] Đã đủ số trận; chuyển sang tác vụ Hồi thành.")
                return True

            x, y = _click_match(device, next_battle)
            log(
                f"[{account.username}] Còn trận tiếp theo; click Trận sau "
                f"tại ({x}, {y}) để chuyển trận."
            )
            hero_deployed = False
            battle_started_at = None
            retreat_requested = False
            awaiting_next_screen = True
            time.sleep(1)
            continue

        if retreat is not None and not hero_deployed:
            log(f"[{account.username}] Phát hiện Rút lui; bắt đầu thả 5 võ tướng.")
            for index, (x, y) in enumerate(hero_points, start=1):
                if not self._wait_if_paused():
                    log(f"[{account.username}] Đã dừng trước khi thả võ tướng {index}.")
                    return False
                if index == 1:
                    # Đồng hồ trận đấu bắt đầu đúng lúc click thả võ tướng đầu tiên.
                    battle_started_at = time.monotonic()
                device.shell(f"input tap {x} {y}")
                log(
                    f"[{account.username}] Thả võ tướng {index}/5 "
                    f"tại ({x}, {y}) — bộ tọa độ {group}."
                )
                time.sleep(0.3)
            hero_deployed = True
            if not self._config.get("task_end_battle") and mode == "normal":
                log(f"[{account.username}] Đã thả đủ võ tướng; hoàn tất Bắt đầu trận.")
                return True
            continue

        if collect is not None:
            should_end = _battle_mode_should_end(
                self._config, mode, screen, templates,
                account=account, log=log,
                battle_started_at=battle_started_at,
            )
            if should_end and not retreat_requested:
                x, y = _click_match(device, collect)
                retreat_requested = True
                log(
                    f"[{account.username}] Điều kiện chế độ {mode} đã đạt; "
                    f"click Thu quân tại ({x}, {y})."
                )
                time.sleep(1)
                if not self._config.get("task_end_battle"):
                    log(
                        f"[{account.username}] Đã click Thu quân theo chế độ {mode}; "
                        "hoàn tất tác vụ Bắt đầu trận."
                    )
                    return True
                continue

        time.sleep(1)

    log(
        f"[{account.username}] Theo dõi Giao Tranh thất bại: "
        "quá thời gian chờ mà không hoàn thành đủ số trận."
    )
    return False


def task_close_battle(self, account, device, ocr_client, log) -> bool:
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


def run(worker, account, steps, device, ocr_client, log, screenshot=None) -> list[str]:
    """Chạy quy trình Giao Tranh theo các tùy chọn được chọn trong GUI."""
    config = worker._config
    selected = [key for key in _TASK_LABELS if config.get(key)]
    if not selected:
        if _STEP_QUAN_SU_GIAO_TRANH in steps:
            steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
        return steps

    if not pre_battle(config, steps, log):
        for key in selected:
            worker.task_progress_changed.emit(_TASK_LABELS[key], "failed", 0, 1)
        return selected

    failed = []
    for key in selected:
        worker.task_progress_changed.emit(_TASK_LABELS[key], "running", 0, 1)

    needs_open = any(
        config.get(key)
        for key in (
            "task_open_battle", "task_use_bazhen",
            "task_find_battle_opponent", "xuat_chien",
        )
    )
    opened = True
    if needs_open:
        try:
            opened = task_open_battle(
                worker, account, device, ocr_client, log, screenshot=screenshot
            )
        except Exception as exc:
            log(f"[{account.username}] Mở Giao Tranh phát sinh lỗi: {exc}")
            opened = False
        if not opened:
            failed.extend(selected)
            for key in selected:
                worker.task_progress_changed.emit(_TASK_LABELS[key], "failed", 0, 1)
        else:
            for key in (
                "task_open_battle", "task_use_bazhen",
                "task_find_battle_opponent", "xuat_chien",
            ):
                if key in selected:
                    worker.task_progress_changed.emit(_TASK_LABELS[key], "done", 1, 1)

    needs_battle = opened and (
        config.get("task_start_battle") or config.get("task_end_battle")
    )
    battle_ok = True
    if needs_battle:
        try:
            battle_ok = battle_run(worker, account, device, ocr_client, log)
        except Exception as exc:
            log(f"[{account.username}] Chạy Giao Tranh phát sinh lỗi: {exc}")
            battle_ok = False
        for key in ("task_start_battle", "task_battle_time_mode"):
            if key in selected:
                worker.task_progress_changed.emit(
                    _TASK_LABELS[key],
                    "done" if battle_ok else "failed",
                    1 if battle_ok else 0,
                    1,
                )
                if not battle_ok:
                    failed.append(key)

    if "task_end_battle" in selected and needs_battle and not battle_ok:
        worker.task_progress_changed.emit(
            _TASK_LABELS["task_end_battle"], "failed", 0, 1
        )
        failed.append("task_end_battle")

    if opened and battle_ok and config.get("task_end_battle"):
        try:
            close_ok = task_close_battle(worker, account, device, ocr_client, log)
        except Exception as exc:
            log(f"[{account.username}] Hồi thành phát sinh lỗi: {exc}")
            close_ok = False
        if close_ok:
            worker.task_progress_changed.emit(
                _TASK_LABELS["task_end_battle"], "done", 1, 1
            )
        else:
            worker.task_progress_changed.emit(
                _TASK_LABELS["task_end_battle"], "failed", 0, 1
            )
            failed.append("task_end_battle")
    for key in selected:
        if key not in (
            "task_open_battle", "task_use_bazhen",
            "task_find_battle_opponent", "xuat_chien",
            "task_start_battle", "task_battle_time_mode", "task_end_battle",
        ):
            continue
        # Các trạng thái đã được phát ở trên; không phát lại.
    if not failed:
        post_battle(log)
    if _STEP_QUAN_SU_GIAO_TRANH in steps:
        steps.remove(_STEP_QUAN_SU_GIAO_TRANH)
    return failed
