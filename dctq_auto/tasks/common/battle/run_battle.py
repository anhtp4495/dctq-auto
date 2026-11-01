"""Thực thi và theo dõi các trận Giao Tranh."""

import time

from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.config.constants import (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_CHIEN_THUAT,
)
from dctq_auto.vision.template_store import get_templates
from dctq_auto.tasks.common.battle.battle_utils import (
    click_match as _click_match,
    match as _match,
    screen_bgr as _screen_bgr,
    swipe as _swipe,
)


_BATTLE_TEMPLATES = (
    _TEMPLATE_QUAN_SU_GIAO_TRANH_RUT_LUI,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_THU_QUAN,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_TRAN_SAU,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_HOI_THANH,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_1_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_2_CO,
    _TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO,
)


def _mode(config) -> str:
    if config.get("giao_tranh_nhanh_1_co"):
        return "fast"
    if config.get("ba_co"):
        return "normal"
    if config.get("task_battle_time_mode"):
        return "time_limit"
    return "normal"


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
    hero_battle_points = [
        positions.get(
            "quan_su.giao_tranh", f"vi_tri_chien_dau_vo_tuong_{index}"
        )
        for index in range(1, 6)
    ]
    drag_point_a = positions.get(
        "quan_su.giao_tranh", "diem_bat_dau_giao_tranh_1"
    )
    drag_point_b = positions.get(
        "quan_su.giao_tranh", "diem_bat_dau_giao_tranh_2"
    )
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

        # Sau khi bấm Xuất chiến, game có thể hiện hộp thoại xác nhận dùng
        # lương thảo nếu tài nguyên không đủ cho lần xuất quân này.
        dung_luong_thao = _match(
            screen,
            templates.get(_TEMPLATE_QUAN_SU_GIAO_TRANH_DUNG_LUONG_THAO),
            account=account, log=log,
        )
        if dung_luong_thao is not None:
            x, y = positions.get(
                "quan_su.giao_tranh", "xac_nhan_dung_luong_thao"
            )
            device.shell(f"input tap {x} {y}")
            log(
                f"[{account.username}] Phát hiện hộp thoại Dùng lương thảo "
                f"(thiếu tài nguyên khi xuất quân); xác nhận tại ({x}, {y})."
            )
            time.sleep(1)
            continue

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
            log(
                f"[{account.username}] Phát hiện Rút lui; chuẩn bị kéo thả 5 võ tướng."
            )

            # Đưa thao tác kéo từ A sang B hai lần để chuẩn bị thả hai võ tướng đầu.
            for repeat in range(1, 3):
                if not self._wait_if_paused():
                    log(f"[{account.username}] Đã dừng khi kéo điểm A -> B ({repeat}/2).")
                    return False
                _swipe(device, drag_point_a, drag_point_b)
                log(
                    f"[{account.username}] Kéo điểm A -> B lần {repeat}/2: "
                    f"{drag_point_a} -> {drag_point_b}."
                )
                time.sleep(0.3)

            # Thời gian trận bắt đầu ngay trước thao tác kéo võ tướng đầu tiên.
            for index in range(2):
                if not self._wait_if_paused():
                    log(f"[{account.username}] Đã dừng trước khi thả võ tướng {index + 1}.")
                    return False
                if index == 0:
                    battle_started_at = time.monotonic()
                source = hero_points[index]
                target = hero_battle_points[index]
                _swipe(device, source, target)
                log(
                    f"[{account.username}] Thả võ tướng {index + 1}/5: "
                    f"{source} -> {target}."
                )
                time.sleep(0.3)

            # Đưa thao tác kéo từ B về A hai lần trước khi thả ba võ tướng còn lại.
            for repeat in range(1, 3):
                if not self._wait_if_paused():
                    log(f"[{account.username}] Đã dừng khi kéo điểm B -> A ({repeat}/2).")
                    return False
                _swipe(device, drag_point_b, drag_point_a)
                log(
                    f"[{account.username}] Kéo điểm B -> A lần {repeat}/2: "
                    f"{drag_point_b} -> {drag_point_a}."
                )
                time.sleep(0.3)

            for index in range(2, 5):
                if not self._wait_if_paused():
                    log(f"[{account.username}] Đã dừng trước khi thả võ tướng {index + 1}.")
                    return False
                source = hero_points[index]
                target = hero_battle_points[index]
                _swipe(device, source, target)
                log(
                    f"[{account.username}] Thả võ tướng {index + 1}/5: "
                    f"{source} -> {target}."
                )
                time.sleep(0.3)

            # Chỉ đánh dấu đã thả sau khi đủ 5 tướng. Trong cùng trận không thả lại.
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

