"""Poller thực hiện toàn bộ quy trình đóng góp Lương thảo."""

import time

import cv2
import numpy as np

from dctq_auto.config.constants import (
    _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_XAC_NHAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
)
from dctq_auto.config.button_positions import ButtonPositions
from dctq_auto.vision.template_store import get_templates

from .base_poller import BaseGuildPoller


_MAX_TRIES = 10
_POLL_INTERVAL = 0.8

# KNB được ưu tiên trước Dùng nhanh: nếu đã hiện thông báo KNB thì không
# tiếp tục thao tác Dùng nhanh nữa.
_RUN_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB,
    _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_XAC_NHAN_DUNG_NHANH,
    _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
)
_CLOSE_TEMPLATES = (
    _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH,
    _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO,
)


class RationsPoller(BaseGuildPoller):
    step_id = _STEP_QUAN_DOAN_DONG_GOP_LUONG_THAO

    category_key = "dong_gop_luong_thao"
    state_by_template = {
        _TEMPLATE_QUAN_DOAN_CHUA_DONG_GOP_LUONG_THAO: "not_donated",
        _TEMPLATE_QUAN_DOAN_DA_DONG_GOP_LUONG_THAO: "donated",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_DONG_GOP_LUONG_THAO: "donation_screen",
        _TEMPLATE_QUAN_DOAN_LAY_THEM_LUONG_THAO_KNB: "buy_rations",
        _TEMPLATE_QUAN_DOAN_DUNG_NHANH: "stop_quickly",
        _TEMPLATE_QUAN_DOAN_XAC_NHAN_DUNG_NHANH: "confirm_stop_quickly",
        _TEMPLATE_QUAN_DOAN_DONG_MAN_HINH_DONG_GOP_LUONG_THAO: "close_donation_screen",
        _TEMPLATE_QUAN_DOAN_MAN_HINH_CHINH: "guild_main",
    }

    def check(self, context) -> dict:
        observation = self._match_first(context)
        observation["requires_action"] = observation["state"] in {
            "not_donated", "donation_screen", "buy_rations",
            "stop_quickly", "confirm_stop_quickly", "close_donation_screen",
        }
        # Đã đóng góp chỉ là hoàn thành phần nghiệp vụ. Chỉ màn hình chính
        # Quân đoàn mới xác nhận toàn bộ task đã kết thúc.
        observation["completed"] = observation["state"] == "guild_main"
        return observation

    @staticmethod
    def _capture(device, account, log):
        try:
            return cv2.cvtColor(
                np.asarray(device.screenshot()), cv2.COLOR_RGB2BGR
            )
        except Exception as exc:
            log(
                f"[{account.display_name}] Không chụp được màn hình "
                f"đóng góp Lương thảo: {exc}"
            )
            return None

    @staticmethod
    def _tap_center(device, matched, account, log, label):
        x = (matched.left + matched.right) // 2
        y = (matched.top + matched.bottom) // 2
        try:
            device.shell(f"input tap {x} {y}")
        except Exception as exc:
            log(
                f"[{account.display_name}] Không click được {label} "
                f"tại ({x}, {y}): {exc}"
            )
            return False
        log(
            f"[{account.display_name}] Click trung điểm {label} "
            f"tại ({x}, {y})."
        )
        return True

    @staticmethod
    def _tap_button(device, account, log, button_name, label):
        x, y = ButtonPositions().get("quan_doan.luong_thao", button_name)
        try:
            device.shell(f"input tap {x} {y}")
        except Exception as exc:
            log(
                f"[{account.display_name}] Không click được {label} "
                f"tại ({x}, {y}): {exc}"
            )
            return False
        log(f"[{account.display_name}] {label} tại ({x}, {y}).")
        return True

    def _observe(self, device, templates, template_names, account, log):
        screen = self._capture(device, account, log)
        if screen is None:
            return None
        return self.check({
            "screen": screen,
            "templates": templates,
            "template_names": template_names,
            "account": account,
            "log": log,
        })

    def run(self, context):
        """Đóng góp, xử lý trường hợp nhận KNB và đóng màn hình nghiệp vụ."""
        worker = context["worker"]
        account = context["account"]
        steps = context["steps"]
        device = context["device"]
        log = context["log"]

        if self.step_id not in steps:
            log(
                f"[{account.display_name}] [Quân đoàn] [Lương thảo] "
                "không có step; bỏ qua."
            )
            return steps

        templates = get_templates(_RUN_TEMPLATES)
        operation_success = False

        log(f"[{account.display_name}] Bắt đầu đóng góp Lương thảo.")

        # Phase 1: thực hiện đóng góp hoặc xác nhận đã nhận KNB.
        for current_try in range(1, _MAX_TRIES + 1):
            if not worker._wait_if_paused():
                log(f"[{account.display_name}] Đóng góp Lương thảo đã dừng theo yêu cầu.")
                return steps

            observation = self._observe(
                device, templates, _RUN_TEMPLATES, account, log
            )
            if observation is None:
                return steps

            state = observation["state"]
            matched = observation["match"]

            if state == "guild_main":
                log(
                    f"[{account.display_name}] Đã nhận diện màn hình chính "
                    "Quân đoàn; đóng góp Lương thảo hoàn tất."
                )
                operation_success = True
                break
            if state == "donated":
                log(f"[{account.display_name}] Đã xác nhận đóng góp Lương thảo.")
                operation_success = True
                break
            if state == "buy_rations":
                log(
                    f"[{account.display_name}] Xuất hiện thông báo lấy thêm "
                    "Lương thảo bằng KNB; bỏ qua thao tác Dùng nhanh."
                )
                operation_success = True
                break
            if state in {"stop_quickly", "confirm_stop_quickly"}:
                label = (
                    "nút Dùng nhanh"
                    if state == "stop_quickly"
                    else "nút xác nhận Dùng nhanh"
                )
                if not self._tap_center(device, matched, account, log, label):
                    return steps
            elif state == "not_donated":
                if not self._tap_center(
                    device, matched, account, log, "nút đóng góp Lương thảo"
                ):
                    return steps
            elif state == "donation_screen":
                if not self._tap_button(
                    device, account, log, "dong_gop",
                    "Thực hiện đóng góp Lương thảo",
                ):
                    return steps
            elif state == "close_donation_screen":
                # Trường hợp đang ở sẵn nút đóng, chuyển sang phase đóng.
                operation_success = True
                break
            else:
                log(
                    f"[{account.display_name}] Không nhận diện được trạng thái "
                    f"đóng góp (lần {current_try}/{_MAX_TRIES}); thử lại."
                )

            time.sleep(_POLL_INTERVAL)

        if not operation_success:
            log(
                f"[{account.display_name}] Không xác nhận được kết quả đóng góp "
                f"sau {_MAX_TRIES} lần thử; giữ nguyên step."
            )
            return steps

        # Phase 2: chỉ coi là kết thúc khi quay lại màn hình chính Quân đoàn.
        close_templates = get_templates(_CLOSE_TEMPLATES)
        for current_try in range(1, _MAX_TRIES + 1):
            if not worker._wait_if_paused():
                log(f"[{account.display_name}] Đã dừng khi đóng màn hình Lương thảo.")
                return steps

            observation = self._observe(
                device, close_templates, _CLOSE_TEMPLATES, account, log
            )
            if observation is None:
                return steps

            state = observation["state"]
            if state == "guild_main":
                steps.remove(self.step_id)
                log(
                    f"[{account.display_name}] Đã xác nhận đóng màn hình "
                    "đóng góp Lương thảo và trở về màn hình chính Quân đoàn."
                )
                log(f"[{account.display_name}] Hoàn tất tác vụ đóng góp Lương thảo.")
                return steps

            if state == "close_donation_screen":
                if not self._tap_center(
                    device, observation["match"], account, log,
                    "nút đóng màn hình đóng góp Lương thảo",
                ):
                    return steps
            else:
                log(
                    f"[{account.display_name}] Chưa thấy nút đóng màn hình "
                    f"đóng góp hoặc màn hình chính (lần {current_try}/{_MAX_TRIES})."
                )

            time.sleep(_POLL_INTERVAL)

        log(
            f"[{account.display_name}] Chưa xác nhận được màn hình chính "
            "Quân đoàn sau khi đóng Lương thảo; giữ nguyên step."
        )
        return steps
