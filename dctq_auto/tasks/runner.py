"""Orchestration of selected real-device tasks and their progress reporting."""

import time
from pathlib import Path
from types import SimpleNamespace

import pytesseract
from PIL import ImageOps

from dctq_auto.adb.client import AdbClient


class UtilityTaskRunnerMixin:
    def _run_utility_tasks(self, device) -> None:
        """Run standalone actions on the currently logged-in game account."""
        from dctq_auto.tasks.common.logout import run_logout_flow

        from dctq_auto.adb.client import AdbClient

        ocr_client = AdbClient(serial=self._serial)
        # Count selected standalone tasks. Battle modes are options that modify
        # "Bắt đầu trận Giao Tranh", not independent tasks; legacy strategy-mode
        # toggles are handled outside this utility-task runner.
        task_labels = (
            ("task_login", "Đăng nhập"),
            ("task_open_activity", "Mở màn hình Hoạt động"),
            ("task_select_phuc_loi", "Chọn Phúc Lợi"),
            ("nhan_le_bao_quoc_van", "Nhận lễ bao quốc vận"),
            ("task_close_activity", "Tắt màn hình Hoạt động"),
            ("diem_danh", "Điểm danh"),
            ("task_enter_guild", "Vào quân đoàn"),
            ("bao_danh_quan_doan", "Báo danh quân đoàn"),
            ("task_receive_lucky_bag", "Nhận túi phúc"),
            ("task_guild_fortune", "Cầu vận quân đoàn (5 lần)"),
            ("dong_gop_knb", "Đóng góp KNB"),
            ("tham_do_lanh_dia", "Thăm dò lãnh địa"),
            ("nhiem_vu_luu_ly_thap", "Lưu Ly Tháp"),
            ("task_open_battle", "Mở màn hình Giao Tranh"),
            ("task_close_battle", "Thoát màn hình Giao Tranh"),
            ("task_use_bazhen", "Sử dụng Canh Bát Trân"),
            ("task_find_battle_opponent", "Tìm đối thủ Giao Tranh"),
            ("task_start_battle", "Bắt đầu trận Giao Tranh"),
            ("task_end_battle", "Kết thúc trận Giao Tranh"),
            ("xuat_chien", "Xuất chiến"),
            ("task_enter_strategy", "Vào màn hình Mưu Binh"),
            ("task_strategy_defense", "Thiết lập phòng thủ"),
            ("task_detect_strategy_status", "Phát hiện trạng thái Mưu Binh"),
            ("task_strategy_vuot_ai", "Vượt Ải"),
            ("task_receive_strategy_reward", "Nhận thưởng Mưu Binh"),
            ("task_close_strategy", "Thoát màn hình Mưu Binh"),
            ("task_close_guild", "Thoát màn hình Quân đoàn"),
            ("task_switch_account", "Đổi tài khoản"),
            ("task_click_coordinates", "Click theo tọa độ"),
        )
        selected = [(key, label) for key, label in task_labels if self._config.get(key)]
        total = len(selected)
        completed = 0
        self.progress_changed.emit(0, max(1, total), "Bắt đầu tác vụ")

        # Gameplay automation for these actions is not implemented in the real
        # ADB flow yet. Report an explicit failed status for each selected task.
        implemented = {
            "task_login", "task_open_activity", "task_select_phuc_loi", "task_close_activity",
            "nhan_le_bao_quoc_van", "diem_danh", "task_enter_guild",
            "bao_danh_quan_doan", "task_receive_lucky_bag", "task_guild_fortune",
            "task_detect_strategy_status", "task_strategy_vuot_ai",
            "task_receive_strategy_reward",
            "task_close_guild", "task_switch_account", "task_click_coordinates",
            "task_open_battle", "task_find_battle_opponent", "task_start_battle", "task_end_battle", "xuat_chien", "task_use_bazhen",
        }
        for key, label in selected:
            if key in implemented:
                continue
            self.log_message.emit(
                f"{label}: LỖI — tác vụ gameplay chưa được triển khai cho ADB thật."
            )
            self.task_progress_changed.emit(label, "failed", 0, 1)
            completed += 1
            self.progress_changed.emit(
                completed, max(1, total), f"Lỗi: {label} chưa triển khai"
            )

        if self._config.get("task_login"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            username = self._config.get("login_username", "")
            password = self._config.get("login_password", "")
            if not username or not password:
                self.log_message.emit("Đăng nhập bị bỏ qua: thiếu username hoặc password.")
                self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                return
            account = SimpleNamespace(username=username, password=password)
            try:
                screen_text = self._screen_text(device)
                if not self._is_login_screen(screen_text):
                    self.log_message.emit(
                        "Không nhập thông tin vì OCR chưa xác nhận màn hình đăng nhập. "
                        "Hãy mở màn hình đăng nhập trong game rồi thử lại."
                    )
                    self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                    return
                from dctq_auto.tasks.common.login import submit_login_form, verify_login
                self.log_message.emit(f"Đang đăng nhập tài khoản {username}.")
                if not submit_login_form(self, account, device, ocr_client):
                    return
                verified, observed_error = verify_login(self, account, device, ocr_client)
                if verified is None:
                    return
                if not verified:
                    self.log_message.emit(
                        "Đăng nhập chưa được xác minh thành công"
                        + (f": {observed_error}" if observed_error else ".")
                    )
                    self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                    return
                completed += 1
                self.task_progress_changed.emit("Đăng nhập", "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đăng nhập thành công")
                self.log_message.emit(f"Đăng nhập tài khoản {username} đã được xác minh.")
            except Exception as exc:
                self.log_message.emit(f"Không thể thực hiện đăng nhập: {exc}")
                self.task_progress_changed.emit("Đăng nhập", "failed", 0, 1)
                return
            finally:
                # Do not retain the password in the worker configuration after use.
                self._config.pop("login_password", None)

        if self._config.get("task_open_activity"):
            label = "Mở màn hình Hoạt động"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_open_activity(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã mở màn hình Hoạt động")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Mở màn hình Hoạt động")

        if self._config.get("task_select_phuc_loi"):
            label = "Chọn Phúc Lợi"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_select_phuc_loi(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã chọn Phúc Lợi")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Chọn Phúc Lợi")

        if self._config.get("nhan_le_bao_quoc_van"):
            label = "Nhận lễ bao quốc vận"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if self._run_receive_quoc_van(device, ocr_client):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã nhận lễ bao Quốc vận"
                )
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Lỗi: Nhận lễ bao Quốc vận"
                )

        if self._config.get("diem_danh"):
            self.task_progress_changed.emit("Điểm danh", "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            if self._run_daily_checkin(device, ocr_client):
                completed += 1
                self.task_progress_changed.emit("Điểm danh", "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã mở mục Điểm danh"
                )
            else:
                self.task_progress_changed.emit("Điểm danh", "failed", 0, 1)
                completed += 1
                self.progress_changed.emit(
                    completed, max(1, total), "Lỗi: Điểm danh"
                )

        if self._config.get("task_close_activity"):
            label = "Tắt màn hình Hoạt động"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_close_activity(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã tắt màn hình Hoạt động")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Tắt màn hình Hoạt động")

        if self._config.get("task_enter_guild"):
            label = "Vào quân đoàn"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi vào Quân đoàn.")
                return
            if self._run_enter_guild(device, ocr_client):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã xác nhận vào Quân đoàn"
                )
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Lỗi: Vào quân đoàn"
                )

        for guild_task_key in (
            "bao_danh_quan_doan",
            "task_receive_lucky_bag",
            "task_guild_fortune",
        ):
            if not self._config.get(guild_task_key):
                continue
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi chạy tác vụ Quân đoàn.")
                return
            task_ok = self._run_guild_screen_task(guild_task_key, device, ocr_client)
            completed += 1
            status_label = {
                "bao_danh_quan_doan": "Báo danh quân đoàn",
                "task_receive_lucky_bag": "Nhận túi phúc",
                "task_guild_fortune": "Cầu vận quân đoàn (5 lần)",
            }[guild_task_key]
            if task_ok:
                self.progress_changed.emit(
                    completed, max(1, total), f"Hoàn tất: {status_label}"
                )
            else:
                # A requested stop is cooperative; don't continue with later actions.
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng theo yêu cầu.")
                    return
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {status_label}"
                )

        if self._config.get("task_open_battle"):
            label = "Mở màn hình Giao Tranh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi mở màn hình Giao Tranh.")
                    return
                # Đọc cấu hình màn hình Giao Tranh từ regions.json để dễ hiệu chỉnh sau này.
                import json

                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                    battle_config = regions_data["regions"]["giao_tranh"]
                    elements = {
                        item["name"]: item for item in battle_config.get("elements", [])
                    }
                    quan_su_center = elements["quan_su"]["center"]
                    button_giao_tranh_center = elements["button_giao_tranh"]["center"]
                    ocr_rect_data = battle_config["ocr_rect"]
                    main_screen_rect_data = battle_config["main_screen_ocr_rect"]
                    x, y = int(quan_su_center["x_px"]), int(quan_su_center["y_px"])
                    button_x = int(button_giao_tranh_center["x_px"])
                    button_y = int(button_giao_tranh_center["y_px"])
                    rect = (
                        int(ocr_rect_data["left"]),
                        int(ocr_rect_data["top"]),
                        int(ocr_rect_data["right"]),
                        int(ocr_rect_data["bottom"]),
                    )
                    main_screen_rect = (
                        int(main_screen_rect_data["left"]),
                        int(main_screen_rect_data["top"]),
                        int(main_screen_rect_data["right"]),
                        int(main_screen_rect_data["bottom"]),
                    )
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"Không đọc được cấu hình Giao Tranh từ {regions_path}: {exc}"
                    ) from exc

                # Bước 1: mở menu Quân Sự bằng tọa độ đã lưu trong regions.json.
                device.shell(f"input tap {x} {y}")
                self.log_message.emit(
                    f"Mở màn hình Giao Tranh — BƯỚC 1: đã click [Quân Sự] tại ({x}, {y})."
                )
                time.sleep(1)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi OCR mục Giao Tranh.")
                    return

                # Bước 2: RECT dùng định dạng (left, top, right, bottom), lấy từ regions.json.
                self.log_message.emit(
                    "Mở màn hình Giao Tranh — BƯỚC 2: OCR RECT "
                    f"{rect}, tìm 'giao_tranh'."
                )
                match = self._tap_ocr_phrase_in_rect(
                    device,
                    ("giao_tranh",),
                    rect,
                    steps=("gray", "white_text"),
                    psm=(6, 7, 11),
                    tap=False,
                )
                if match is None:
                    raise RuntimeError(
                        f"OCR không tìm thấy 'giao_tranh' trong RECT {rect}; không click."
                    )
                _ocr_x, _ocr_y, found_rect = match
                # OCR chỉ xác nhận nhãn hợp lệ; điểm click luôn lấy từ regions.json.
                device.shell(f"input tap {button_x} {button_y}")
                self.log_message.emit(
                    "OCR xác nhận 'giao_tranh' hợp lệ — "
                    f"RECT {found_rect}; click button_giao_tranh tại ({button_x}, {button_y})."
                )
                time.sleep(0.8)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi xác minh giao diện chính Giao Tranh.")
                    return

                # Bước 3: chỉ xác nhận mở đúng màn hình khi OCR thấy tim_doi_thu.
                self.log_message.emit(
                    "Mở màn hình Giao Tranh — BƯỚC 3: OCR RECT "
                    f"{main_screen_rect}, tìm 'tim_doi_thu'."
                )
                main_screen_match = self._tap_ocr_phrase_in_rect(
                    device,
                    ("tim_doi_thu",),
                    main_screen_rect,
                    steps=("gray", "white_text"),
                    psm=(11,),
                    tap=False,
                )
                if main_screen_match is None:
                    raise RuntimeError(
                        "OCR không tìm thấy 'tim_doi_thu' trong RECT "
                        f"{main_screen_rect}; chưa xác nhận giao diện chính Giao Tranh."
                    )
                _target_x, _target_y, main_screen_found_rect = main_screen_match
                self.log_message.emit(
                    "Bước 3 xác nhận đang ở giao diện chính Giao Tranh: "
                    f"tìm thấy 'tim_doi_thu' — RECT {main_screen_found_rect}."
                )

                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã click mục Giao Tranh"
                )
                self.log_message.emit(
                    "Bước 2 thành công: OCR xác nhận 'giao_tranh' và đã click button_giao_tranh theo tọa độ đã lưu."
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )

        if self._config.get("task_use_bazhen"):
            label = "Sử dụng Canh Bát Trân"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                import json

                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                    elements = {
                        item["name"]: item
                        for item in regions_data["regions"]["giao_tranh"].get("elements", [])
                    }
                    center = elements["su_dung_canh_bat_tran"]["center"]
                    x, y = int(center["x_px"]), int(center["y_px"])
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"Không đọc được tọa độ Sử dụng Canh Bát Trân từ {regions_path}: {exc}"
                    ) from exc

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi sử dụng Canh Bát Trân.")
                    return
                device.shell(f"input tap {x} {y}")
                self.log_message.emit(
                    f"Sử dụng Canh Bát Trân: đã click tọa độ cấu hình ({x}, {y})."
                )
                time.sleep(0.5)
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã hoàn tất Sử dụng Canh Bát Trân"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )

        if self._config.get("task_find_battle_opponent"):
            label = "Tìm đối thủ Giao Tranh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                import json

                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                    battle_config = regions_data["regions"]["giao_tranh"]
                    elements = {
                        item["name"]: item for item in battle_config.get("elements", [])
                    }
                    find_opponent = elements["tim_doi_thu"]["center"]
                    find_x, find_y = int(find_opponent["x_px"]), int(find_opponent["y_px"])
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"Không đọc được tọa độ Tìm đối thủ từ {regions_path}: {exc}"
                    ) from exc

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi click Tìm đối thủ.")
                    return
                device.shell(f"input tap {find_x} {find_y}")
                self.log_message.emit(
                    f"Tìm đối thủ Giao Tranh — click [tim_doi_thu] tại ({find_x}, {find_y})."
                )
                time.sleep(0.5)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi kiểm tra xác nhận tìm đối thủ.")
                    return

                # Bước 3: nếu xuất hiện hộp xác nhận thì click; nếu không có,
                # coi như đã vào trận và bỏ qua xác nhận.
                confirm_rect = (617, 644, 1292, 722)
                self.log_message.emit(
                    "Tìm đối thủ Giao Tranh — BƯỚC 3: OCR RECT "
                    f"{confirm_rect}, tìm 'xac_nhan'."
                )
                confirm_match = self._tap_ocr_phrase_in_rect(
                    device,
                    ("xac_nhan",),
                    confirm_rect,
                    steps=("gray", "white_text"),
                    psm=(11,),
                )
                if confirm_match is None:
                    self.log_message.emit(
                        "Không tìm thấy 'xac_nhan' trong hộp xác nhận; "
                        "coi như đã ở trong trận, bỏ qua xác nhận."
                    )
                else:
                    confirm_x, confirm_y, confirm_found_rect = confirm_match
                    self.log_message.emit(
                        "Đã tìm thấy và click 'xac_nhan' tại "
                        f"({confirm_x}, {confirm_y}); RECT OCR {confirm_found_rect}."
                    )

                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã hoàn tất Tìm đối thủ Giao Tranh"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )

        if self._config.get("xuat_chien"):
            label = "Xuất chiến"
            self.task_progress_changed.emit(label, "running", 0, 1)
            rect = (1433, 970, 1614, 1016)
            try:
                # Thử OCR tối đa 3 lần; chỉ click khi OCR xác nhận được nút.
                match = None
                for attempt in range(1, 4):
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng trước khi thực hiện Xuất chiến.")
                        return
                    self.log_message.emit(
                        f"Xuất chiến — lần thử {attempt}/3: OCR RECT {rect}, "
                        "tìm 'xuat_chien'."
                    )
                    match = self._tap_ocr_phrase_in_rect(
                        device,
                        ("xuat_chien",),
                        rect,
                        steps=("gray", "white_text"),
                        psm=(11,),
                    )
                    if match is not None:
                        x, y, found_rect = match
                        self.log_message.emit(
                            f"Đã phát hiện và click 'xuat_chien' tại ({x}, {y}); "
                            f"RECT nhận diện {found_rect}."
                        )
                        break
                    self.log_message.emit(
                        f"Lần thử {attempt}/3 chưa OCR được 'xuat_chien'."
                    )
                    if attempt < 3:
                        time.sleep(0.5)
                if match is None:
                    raise RuntimeError(
                        f"Không phát hiện được 'xuat_chien' sau 3 lần OCR tại RECT {rect}."
                    )
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã hoàn tất Xuất chiến"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )

        if self._config.get("task_start_battle"):
            label = "Bắt đầu trận Giao Tranh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                import json

                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                    elements = {
                        item["name"]: item
                        for item in regions_data["regions"]["giao_tranh"].get("elements", [])
                    }
                    point_a = elements["bat_dau_tran_diem_a"]["center"]
                    point_b = elements["bat_dau_tran_diem_b"]["center"]
                    start_x, start_y = int(point_a["x_px"]), int(point_a["y_px"])
                    end_x, end_y = int(point_b["x_px"]), int(point_b["y_px"])
                    duration_ms = int(
                        regions_data["regions"]["giao_tranh"].get("start_battle_swipe_duration_ms", 500)
                    )
                    if duration_ms <= 0:
                        raise ValueError("thời gian kéo phải lớn hơn 0")
                    hero_points = {f"vo_tuong_{index}": elements[f"vo_tuong_{index}"]["center"] for index in range(1, 6)}
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"Không đọc được cấu hình kéo Bắt đầu trận từ {regions_path}: {exc}"
                    ) from exc

                # BƯỚC 1: OCR chỉ báo để chọn bộ tọa độ võ tướng; không click.
                account_key = str(self._config.get("login_username", "")).strip() or "__current_account_unspecified__"
                cache = getattr(self, "_battle_hero_flag_cache", {})
                if account_key not in cache:
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng trước OCR xác định bộ võ tướng.")
                        return
                    screenshot = device.screenshot().convert("RGB")
                    roi = screenshot.crop((302, 978, 411, 1009)).convert("L")
                    ocr_text = pytesseract.image_to_string(roi, config="--psm 8").strip()
                    cache[account_key] = bool(ocr_text)
                    self._battle_hero_flag_cache = cache
                    self.log_message.emit(
                        f"OCR chỉ báo võ tướng cho tài khoản '{account_key}': "
                        f"text={ocr_text!r}, kết quả={'TRUE' if cache[account_key] else 'FALSE'}."
                    )
                else:
                    self.log_message.emit(
                        f"Dùng cache OCR võ tướng cho tài khoản '{account_key}': "
                        f"{'TRUE' if cache[account_key] else 'FALSE'}."
                    )
                has_hero_text = cache[account_key]
                suffix = "" if has_hero_text else "_1"
                hero_points = {
                    f"vo_tuong_{index}{suffix}": elements[f"vo_tuong_{index}{suffix}"]["center"]
                    for index in range(1, 6)
                }
                self.log_message.emit(
                    "Bắt đầu trận Giao Tranh — BƯỚC 1: đã chọn bộ tọa độ "
                    + ("TRUE" if has_hero_text else "FALSE") + ": "
                    + ", ".join(
                        f"{name}=({int(point['x_px'])}, {int(point['y_px'])})"
                        for name, point in hero_points.items()
                    )
                    + "; chỉ lưu tọa độ, không click."
                )


                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước Bước 2 kéo để bắt đầu trận Giao Tranh.")
                    return
                device.shell(
                    f"input swipe {start_x} {start_y} {end_x} {end_y} {duration_ms}"
                )
                self.log_message.emit(
                    "Bắt đầu trận Giao Tranh — BƯỚC 2: kéo từ điểm A "
                    f"({start_x}, {start_y}) đến điểm B ({end_x}, {end_y}) "
                    f"trong {duration_ms} ms."
                )
                time.sleep(0.5)

                # BƯỚC 3: click võ tướng 1, b2.1, võ tướng 2, rồi b2.2.
                click_sequence = [
                    (f"vo_tuong_1{suffix}", hero_points[f"vo_tuong_1{suffix}"]),
                    ("vi_tri_chien_dau_vo_tuong_1", elements["vi_tri_chien_dau_vo_tuong_1"]["center"]),
                    (f"vo_tuong_2{suffix}", hero_points[f"vo_tuong_2{suffix}"]),
                    ("vi_tri_chien_dau_vo_tuong_2", elements["vi_tri_chien_dau_vo_tuong_2"]["center"]),
                ]
                for step_index, (point_name, point) in enumerate(click_sequence, start=1):
                    if not self._wait_if_paused():
                        self.log_message.emit(
                            f"Đã dừng trước Bước 3.{step_index} ({point_name}) của Bắt đầu trận Giao Tranh."
                        )
                        return
                    x, y = int(point["x_px"]), int(point["y_px"])
                    device.shell(f"input tap {x} {y}")
                    self.log_message.emit(
                        f"Bắt đầu trận Giao Tranh — BƯỚC 3.{step_index}: click {point_name} tại ({x}, {y})."
                    )
                    time.sleep(0.3)

                # BƯỚC 4: swipe từ b3.1 đến b3.3 theo tọa độ đã lưu.
                point_31 = elements["bat_dau_tran_b3_1"]["center"]
                point_33 = elements["bat_dau_tran_b3_3"]["center"]
                b31_x, b31_y = int(point_31["x_px"]), int(point_31["y_px"])
                b33_x, b33_y = int(point_33["x_px"]), int(point_33["y_px"])
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước Bước 4 của Bắt đầu trận Giao Tranh.")
                    return
                for swipe_index in range(2):
                    if not self._wait_if_paused():
                        self.log_message.emit(
                            f"Đã dừng trước lần swipe {swipe_index + 1}/2 của Bước 4 Bắt đầu trận Giao Tranh."
                        )
                        return
                    device.shell(f"input swipe {b31_x} {b31_y} {b33_x} {b33_y} {duration_ms}")
                    self.log_message.emit(
                        f"Bắt đầu trận Giao Tranh — BƯỚC 4: swipe lần {swipe_index + 1}/2 từ "
                        f"({b31_x}, {b31_y}) đến ({b33_x}, {b33_y}) trong {duration_ms} ms."
                    )
                    time.sleep(0.5)

                # BƯỚC 5: lần lượt click võ tướng 3, b2.3, võ tướng 4, b2.4,
                # võ tướng 5, b2.5. Mỗi lần click cách nhau 300 ms.
                click_sequence_step5 = [
                    (f"vo_tuong_3{suffix}", hero_points[f"vo_tuong_3{suffix}"]),
                    ("vi_tri_chien_dau_vo_tuong_3", elements["vi_tri_chien_dau_vo_tuong_3"]["center"]),
                    (f"vo_tuong_4{suffix}", hero_points[f"vo_tuong_4{suffix}"]),
                    ("vi_tri_chien_dau_vo_tuong_4", elements["vi_tri_chien_dau_vo_tuong_4"]["center"]),
                    (f"vo_tuong_5{suffix}", hero_points[f"vo_tuong_5{suffix}"]),
                    ("vi_tri_chien_dau_vo_tuong_5", elements["vi_tri_chien_dau_vo_tuong_5"]["center"]),
                ]
                for step_index, (point_name, point) in enumerate(click_sequence_step5, start=1):
                    if not self._wait_if_paused():
                        self.log_message.emit(
                            f"Đã dừng trước Bước 5.{step_index} ({point_name}) của Bắt đầu trận Giao Tranh."
                        )
                        return
                    x, y = int(point["x_px"]), int(point["y_px"])
                    device.shell(f"input tap {x} {y}")
                    self.log_message.emit(
                        f"Bắt đầu trận Giao Tranh — BƯỚC 5.{step_index}: click {point_name} tại ({x}, {y})."
                    )
                    time.sleep(0.3)

                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã hoàn tất Bước 1 đến Bước 5 Bắt đầu trận Giao Tranh"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )


        if self._config.get("task_start_battle") and self._config.get("task_battle_time_mode", False):
            label = "Thời gian tối đa Giao Tranh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                time_limit = int(self._config.get("task_battle_time_limit", 15))
                if time_limit <= 0:
                    raise ValueError("Thời gian tối đa phải lớn hơn 0 giây")
                import json
                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                elements = {
                    item["name"]: item
                    for item in regions_data["regions"]["giao_tranh"].get("elements", [])
                }
                account_key = str(self._config.get("login_username", "")).strip() or "__current_account_unspecified__"
                has_hero_text = getattr(self, "_battle_hero_flag_cache", {}).get(account_key)
                if has_hero_text is None:
                    raise RuntimeError("Chưa có kết quả OCR chọn bộ tọa độ võ tướng từ tác vụ Bắt đầu trận Giao Tranh.")
                suffix = "" if has_hero_text else "_1"
                hero_points = {
                    f"vo_tuong_{index}{suffix}": elements[f"vo_tuong_{index}{suffix}"]["center"]
                    for index in range(1, 6)
                }

                def wait_battle_seconds(seconds: int) -> bool:
                    deadline = time.monotonic() + seconds
                    while True:
                        if not self._wait_if_paused():
                            return False
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return True
                        time.sleep(min(0.25, remaining))

                self.log_message.emit(
                    f"Thời gian tối đa Giao Tranh — chờ đủ {time_limit} giây kể từ sau khi bắt đầu trận."
                )
                if time_limit > 10:
                    if not wait_battle_seconds(10):
                        self.log_message.emit("Đã dừng trong thời gian chờ 10 giây của Giao Tranh.")
                        return
                    for hero_index in range(1, 6):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng khi click lại đội hình võ tướng.")
                            return
                        point_name = f"vo_tuong_{hero_index}{suffix}"
                        point = hero_points[point_name]
                        hero_x, hero_y = int(point["x_px"]), int(point["y_px"])
                        device.shell(f"input tap {hero_x} {hero_y}")
                        self.log_message.emit(
                            f"Thời gian tối đa Giao Tranh — click {point_name} tại ({hero_x}, {hero_y})."
                        )
                        time.sleep(0.3)
                    remaining_seconds = max(0, time_limit - 10 - 1)
                else:
                    remaining_seconds = time_limit
                if remaining_seconds and not wait_battle_seconds(remaining_seconds):
                    self.log_message.emit("Đã dừng khi chờ đủ thời gian Giao Tranh.")
                    return
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), f"Hoàn tất {label} ({time_limit} giây)")
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), f"Lỗi: {label}")
        if self._config.get("task_end_battle"):
            label = "Kết thúc trận Giao Tranh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                import json

                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                    battle_config = regions_data["regions"]["giao_tranh"]
                    elements = {
                        item["name"]: item
                        for item in battle_config.get("elements", [])
                    }
                    start_swipe_duration_ms = int(
                        battle_config.get("start_battle_swipe_duration_ms", 500)
                    )
                    if start_swipe_duration_ms <= 0:
                        raise ValueError("thời gian kéo phải lớn hơn 0")
                    end_rect_data = battle_config["end_battle_ocr_rect"]
                    confirm_rect_data = battle_config["retreat_confirm_ocr_rect"]
                    end_rect = (
                        int(end_rect_data["left"]), int(end_rect_data["top"]),
                        int(end_rect_data["right"]), int(end_rect_data["bottom"]),
                    )
                    confirm_rect = (
                        int(confirm_rect_data["left"]), int(confirm_rect_data["top"]),
                        int(confirm_rect_data["right"]), int(confirm_rect_data["bottom"]),
                    )
                    target_battles = max(1, int(self._config.get("task_open_battle_count", 1)))
                    button_points = {
                        name: (
                            int(elements[name]["center"]["x_px"]),
                            int(elements[name]["center"]["y_px"]),
                        )
                        for name in (
                            "button_thu_quan", "button_xac_nhan",
                            "button_tran_sau", "button_hoi_thanh",
                        )
                    }
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError(
                        f"Không đọc được cấu hình kết thúc trận Giao Tranh từ {regions_path}: {exc}"
                    ) from exc

                def read_rect_text(rect):
                    words = self._ocr_words_in_rect(
                        device, rect, steps=("gray", "white_text"), psm=(11,)
                    )
                    return " ".join(
                        str(word.get("text", "")).strip()
                        for word in words if str(word.get("text", "")).strip()
                    )

                def has_text(text, expected):
                    normalized = self._normalize_screen_text(text)
                    compact = normalized.replace(" ", "")
                    return expected in normalized or expected.replace(" ", "") in compact

                def start_next_battle():
                    """Re-run the configured start-battle sequence after selecting the next battle."""
                    account_key = (
                        str(self._config.get("login_username", "")).strip()
                        or "__current_account_unspecified__"
                    )
                    cache = getattr(self, "_battle_hero_flag_cache", {})
                    if account_key not in cache:
                        if not self._wait_if_paused():
                            raise RuntimeError("Đã dừng trước OCR xác định bộ võ tướng.")
                        screenshot = device.screenshot().convert("RGB")
                        roi = screenshot.crop((302, 978, 411, 1009)).convert("L")
                        ocr_text = pytesseract.image_to_string(roi, config="--psm 8").strip()
                        cache[account_key] = bool(ocr_text)
                        self._battle_hero_flag_cache = cache
                        self.log_message.emit(
                            f"Bắt đầu trận Giao Tranh lại — OCR chỉ báo võ tướng: "
                            f"text={ocr_text!r}, kết quả={'TRUE' if cache[account_key] else 'FALSE'}."
                        )
                    has_hero_text = cache[account_key]
                    suffix = "" if has_hero_text else "_1"
                    hero_points = {
                        f"vo_tuong_{index}{suffix}": elements[f"vo_tuong_{index}{suffix}"]["center"]
                        for index in range(1, 6)
                    }

                    point_a = elements["bat_dau_tran_diem_a"]["center"]
                    point_b = elements["bat_dau_tran_diem_b"]["center"]
                    start_x, start_y = int(point_a["x_px"]), int(point_a["y_px"])
                    end_x, end_y = int(point_b["x_px"]), int(point_b["y_px"])
                    if not self._wait_if_paused():
                        raise RuntimeError("Đã dừng trước khi kéo để bắt đầu trận tiếp theo.")
                    device.shell(
                        f"input swipe {start_x} {start_y} {end_x} {end_y} "
                        f"{start_swipe_duration_ms}"
                    )
                    self.log_message.emit(
                        f"Bắt đầu trận Giao Tranh lại — kéo từ ({start_x}, {start_y}) "
                        f"đến ({end_x}, {end_y}) trong {start_swipe_duration_ms} ms."
                    )
                    time.sleep(3.0)

                    click_sequence = [
                        (f"vo_tuong_1{suffix}", hero_points[f"vo_tuong_1{suffix}"]),
                        ("vi_tri_chien_dau_vo_tuong_1", elements["vi_tri_chien_dau_vo_tuong_1"]["center"]),
                        (f"vo_tuong_2{suffix}", hero_points[f"vo_tuong_2{suffix}"]),
                        ("vi_tri_chien_dau_vo_tuong_2", elements["vi_tri_chien_dau_vo_tuong_2"]["center"]),
                    ]
                    for point_name, point in click_sequence:
                        if not self._wait_if_paused():
                            raise RuntimeError(f"Đã dừng trước thao tác {point_name} của trận tiếp theo.")
                        x, y = int(point["x_px"]), int(point["y_px"])
                        device.shell(f"input tap {x} {y}")
                        self.log_message.emit(
                            f"Bắt đầu trận Giao Tranh lại — click {point_name} tại ({x}, {y})."
                        )
                        time.sleep(3.0)

                    point_31 = elements["bat_dau_tran_b3_1"]["center"]
                    point_33 = elements["bat_dau_tran_b3_3"]["center"]
                    b31_x, b31_y = int(point_31["x_px"]), int(point_31["y_px"])
                    b33_x, b33_y = int(point_33["x_px"]), int(point_33["y_px"])
                    for swipe_index in range(2):
                        if not self._wait_if_paused():
                            raise RuntimeError("Đã dừng khi kéo đội hình trận tiếp theo.")
                        device.shell(
                            f"input swipe {b31_x} {b31_y} {b33_x} {b33_y} "
                            f"{start_swipe_duration_ms}"
                        )
                        self.log_message.emit(
                            f"Bắt đầu trận Giao Tranh lại — kéo đội hình lần "
                            f"{swipe_index + 1}/2 từ ({b31_x}, {b31_y}) đến "
                            f"({b33_x}, {b33_y}) trong {start_swipe_duration_ms} ms."
                        )
                        time.sleep(3.0)

                    click_sequence = [
                        item
                        for index in (3, 4, 5)
                        for item in (
                            (f"vo_tuong_{index}{suffix}", hero_points[f"vo_tuong_{index}{suffix}"]),
                            (
                                f"vi_tri_chien_dau_vo_tuong_{index}",
                                elements[f"vi_tri_chien_dau_vo_tuong_{index}"]["center"],
                            ),
                        )
                    ]
                    for point_name, point in click_sequence:
                        if not self._wait_if_paused():
                            raise RuntimeError(f"Đã dừng trước thao tác {point_name} của trận tiếp theo.")
                        x, y = int(point["x_px"]), int(point["y_px"])
                        device.shell(f"input tap {x} {y}")
                        self.log_message.emit(
                            f"Bắt đầu trận Giao Tranh lại — click {point_name} tại ({x}, {y})."
                        )
                        time.sleep(3.0)
                    self.log_message.emit(
                        f"Đã thực hiện xong chuỗi Bắt đầu trận Giao Tranh cho trận {current_battle}."
                    )

                current_battle = 1
                finished = False
                self.log_message.emit(
                    f"Kết thúc trận Giao Tranh: mục tiêu {target_battles} trận; "
                    f"OCR RECT trạng thái {end_rect}, hộp xác nhận {confirm_rect}."
                )
                while current_battle <= target_battles:
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng theo yêu cầu khi kết thúc trận Giao Tranh.")
                        return

                    deadline = time.monotonic() + 180
                    detected_text = ""
                    last_ocr_report = None
                    last_ocr_report_at = 0.0
                    # Sau khi xác nhận thu quân, không click nút này lần nữa
                    # chỉ vì OCR còn đọc thấy chữ cũ trong lúc giao diện chuyển cảnh.
                    retreat_confirmed = False
                    while time.monotonic() < deadline:
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng theo yêu cầu khi OCR trạng thái trận.")
                            return

                        detected_text = read_rect_text(end_rect)
                        # Ghi log chẩn đoán khi OCR đổi kết quả, hoặc tối đa mỗi 5 giây.
                        # Không tạo mục tiến trình riêng "Chờ giao tranh"; tác vụ vẫn là
                        # một mục duy nhất: "Kết thúc trận Giao Tranh".
                        now = time.monotonic()
                        ocr_report = detected_text.strip() or "(trống)"
                        if ocr_report != last_ocr_report or now - last_ocr_report_at >= 5:
                            self.log_message.emit(
                                f"Kết thúc trận Giao Tranh — OCR RECT {end_rect}: "
                                f"{ocr_report[:180]}; tiếp tục kiểm tra trạng thái trận."
                            )
                            last_ocr_report = ocr_report
                            last_ocr_report_at = now

                        if has_text(detected_text, "thu quan") and not retreat_confirmed:
                            x, y = button_points["button_thu_quan"]
                            device.shell(f"input tap {x} {y}")
                            self.log_message.emit(
                                "OCR phát hiện 'thu_quan' trong "
                                f"RECT {end_rect}; click button_thu_quan tại ({x}, {y})."
                            )
                            time.sleep(3.0)

                            confirm_text = ""
                            confirmed = False
                            # Chờ 3 giây trước mỗi lần OCR hộp thoại xác nhận.
                            # Thử tối đa 4 lần: lần đầu và thêm 3 lần nếu chưa thấy.
                            for confirm_attempt in range(1, 5):
                                if not self._wait_if_paused():
                                    self.log_message.emit("Đã dừng trước khi xác nhận Rút lui.")
                                    return
                                time.sleep(3.0)
                                confirm_text = read_rect_text(confirm_rect)
                                self.log_message.emit(
                                    f"OCR hộp thoại Rút lui lần {confirm_attempt}/4 — "
                                    f"RECT {confirm_rect}: {confirm_text[:160] or '(trống)'}."
                                )
                                if has_text(confirm_text, "thu quan"):
                                    confirm_x, confirm_y = button_points["button_xac_nhan"]
                                    device.shell(f"input tap {confirm_x} {confirm_y}")
                                    self.log_message.emit(
                                        "OCR xác nhận 'thu_quan' trong hộp thoại Rút lui; "
                                        f"click button_xac_nhan tại ({confirm_x}, {confirm_y})."
                                    )
                                    time.sleep(3.0)
                                    confirmed = True
                                    retreat_confirmed = True
                                    break
                            if not confirmed:
                                raise RuntimeError(
                                    "Đã click Rút lui nhưng OCR không tìm thấy 'thu_quan' "
                                    f"trong RECT {confirm_rect}. OCR: {confirm_text[:160] or '(trống)'}"
                                )
                            # Sau xác nhận Rút lui, tiếp tục chờ kết quả có nút tran_sau.
                            continue

                        if has_text(detected_text, "tran sau"):
                            self.log_message.emit(
                                f"OCR phát hiện 'tran_sau' (trận {current_battle}/{target_battles})."
                            )
                            if current_battle < target_battles:
                                x, y = button_points["button_tran_sau"]
                                device.shell(f"input tap {x} {y}")
                                self.log_message.emit(
                                    f"Trận {current_battle}/{target_battles}: còn trận cần đánh; "
                                    f"click button_tran_sau tại ({x}, {y})."
                                )
                                current_battle += 1
                                self.log_message.emit(
                                    f"Đã tăng số trận hiện tại lên {current_battle}/{target_battles}."
                                )
                                if self._config.get("task_start_battle"):
                                    time.sleep(3.0)
                                    start_next_battle()
                                    # Tiếp tục OCR để theo dõi kết quả của trận vừa bắt đầu.
                                    break
                                self.log_message.emit(
                                    "Không chọn 'Bắt đầu trận Giao Tranh'; xem như tác vụ "
                                    "'Kết thúc trận Giao Tranh' đã hoàn tất sau khi chọn trận tiếp theo."
                                )
                                finished = True
                                break

                            x, y = button_points["button_hoi_thanh"]
                            device.shell(f"input tap {x} {y}")
                            self.log_message.emit(
                                f"Đã đủ {target_battles}/{target_battles} trận; "
                                f"click button_hoi_thanh tại ({x}, {y})."
                            )
                            finished = True
                            time.sleep(3.0)
                            break

                        time.sleep(3.0)
                    else:
                        raise RuntimeError(
                            "Hết 180 giây nhưng OCR không phát hiện được 'thu_quan' "
                            f"hoặc 'tran_sau' trong RECT {end_rect}. "
                            f"OCR cuối: {detected_text[:180] or '(trống)'}"
                        )

                    if finished:
                        break

                if not finished:
                    raise RuntimeError("Chưa xác nhận được thao tác Hồi thành sau số trận mục tiêu.")
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), "Đã kết thúc đủ số trận Giao Tranh"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )
        if self._config.get("task_detect_strategy_status"):
            label = "Phát hiện trạng thái Mưu Binh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                _regions_path, elements = self._strategy_regions()
                status, stage = self._detect_strategy_status(device, elements)
                if status == "khong_xac_dinh":
                    raise RuntimeError("OCR chưa xác định được trạng thái Mưu Binh.")
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Trạng thái Mưu Binh: {status}"
                )
            except Exception as exc:
                completed += 1
                self.log_message.emit(f"{label} thất bại: {exc}")
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Lỗi: {label}"
                )

        if self._config.get("task_strategy_vuot_ai"):
            label = "Vượt Ải"
            self.task_progress_changed.emit(label, "running", 0, 1)
            if self._run_strategy_vuot_ai(device):
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Hoàn tất Vượt Ải")
            else:
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), "Lỗi: Vượt Ải")

        if self._config.get("task_receive_strategy_reward"):
            label = "Nhận thưởng Mưu Binh"
            self.task_progress_changed.emit(label, "running", 0, 1)
            try:
                _regions_path, elements = self._strategy_regions()
                reward_ok = self._run_strategy_reward(device, elements)
            except Exception as exc:
                self.log_message.emit(f"{label} thất bại: {exc}")
                reward_ok = False
            completed += 1
            if reward_ok:
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã nhận thưởng Mưu Binh")
            else:
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), f"Lỗi: {label}")

        if self._config.get("task_close_guild"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi thoát màn hình Quân đoàn.")
                return
            try:
                import json

                regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
                try:
                    regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Không đọc được {regions_path}: {exc}") from exc

                self.log_message.emit(
                    "Thoát Quân đoàn — BƯỚC 1: Đóng màn hình Quân đoàn bằng close_quan_doan "
                    "lấy từ regions.json."
                )
                ocr_client.tap_ocr_target("close_quan_doan", regions_path=regions_path)
                self.log_message.emit(
                    "Đã đóng màn hình Quân đoàn; chờ 5 giây trước khi OCR nút "
                    "'vao_quan_doan' trong RECT (1270, 968, 1532, 1026)."
                )
                time.sleep(5)

                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trước khi kiểm tra nút vào Quân đoàn.")
                    return

                # Chỉ OCR vùng nút "Vào quân đoàn", tránh chữ trong khung chat
                # làm nhiễu kết quả. RECT có dạng (left, top, right, bottom).
                rect = (1270, 968, 1532, 1026)
                screenshot = device.screenshot().convert("RGB")
                if screenshot.width < rect[2] or screenshot.height < rect[3]:
                    raise RuntimeError(
                        f"Screenshot {screenshot.width}x{screenshot.height} nhỏ hơn RECT {rect}"
                    )
                roi = ImageOps.autocontrast(
                    screenshot.crop(rect).convert("L")
                )
                recognized_texts = []
                for language in ("vie+eng", "eng"):
                    language_failed = False
                    for page_mode in (6, 11):
                        try:
                            text = pytesseract.image_to_string(
                                roi, lang=language, config=f"--psm {page_mode}"
                            ).strip()
                        except pytesseract.TesseractError:
                            language_failed = True
                            break
                        if text and text not in recognized_texts:
                            recognized_texts.append(text)
                    if not language_failed and recognized_texts:
                        break
                screen_text = " ".join(recognized_texts)
                normalized = self._normalize_screen_text(screen_text)
                has_enter_guild_label = "vao quan doan" in normalized
                if has_enter_guild_label:
                    self.log_message.emit(
                        "Thoát Quân đoàn — OCR tìm thấy 'vao_quan_doan'; "
                        "click tọa độ thoat_chat_quan_doan đã lưu trong regions.json."
                    )
                    x, y = ocr_client.tap_ocr_target(
                        "thoat_chat_quan_doan", regions_path=regions_path
                    )
                    self.log_message.emit(
                        f"Đã click thoat_chat_quan_doan tại ({x}, {y})."
                    )
                    time.sleep(0.8)
                else:
                    self.log_message.emit(
                        "OCR không tìm thấy 'vao_quan_doan'; bỏ qua click "
                        "thoat_chat_quan_doan vì không cần đóng chat theo điều kiện đã đặt. "
                        f"OCR: {screen_text[:220] or '(trống)'}"
                    )

                completed += 1
                self.progress_changed.emit(
                    completed, max(1, total), "Đã xử lý trạng thái chat Quân đoàn"
                )
                self.task_progress_changed.emit(
                    "Thoát màn hình Quân đoàn", "done", 1, 1
                )
                self.log_message.emit(
                    "Hoàn tất flow thoát Quân đoàn: kiểm tra 'vao_quan_doan'; "
                    "nếu có thì click thoat_chat_quan_doan theo regions.json."
                )
            except Exception as exc:
                self.log_message.emit(
                    f"Không đóng được giao diện Quân đoàn/chat: {exc}"
                )
                self.task_progress_changed.emit(
                    "Thoát màn hình Quân đoàn", "failed", 0, 1
                )

        if self._config.get("task_switch_account"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            self.log_message.emit(
                "Tác vụ: bắt đầu quy trình Đổi tài khoản; "
                "chỉ xác nhận khi OCR nhận diện đúng hộp thoại."
            )
            account = SimpleNamespace(username="Tác vụ")
            result = run_logout_flow(self, account, device, ocr_client)
            if result:
                completed += 1
                self.task_progress_changed.emit("Đổi tài khoản", "done", 1, 1)
                self.log_message.emit(
                    "Tác vụ Đổi tài khoản đã hoàn tất và đã xác minh màn hình đăng nhập."
                )
            elif result is None:
                self.log_message.emit("Tác vụ Đổi tài khoản đã dừng theo yêu cầu.")
                return
            else:
                self.log_message.emit(
                    "Tác vụ Đổi tài khoản chưa xác minh hoàn tất; kiểm tra nhật ký OCR."
                )
                self.task_progress_changed.emit("Đổi tài khoản", "failed", 0, 1)
            self.progress_changed.emit(
                completed, max(1, total), "Đổi tài khoản đã xử lý"
            )

        if self._config.get("task_click_coordinates"):
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng theo yêu cầu.")
                return
            x = int(self._config.get("task_click_x", 0))
            y = int(self._config.get("task_click_y", 0))
            try:
                device.shell(f"input tap {x} {y}")
                completed += 1
                self.task_progress_changed.emit("Click theo tọa độ", "done", 1, 1)
                self.progress_changed.emit(
                    completed, max(1, total), f"Đã click tọa độ ({x}, {y})"
                )
                self.log_message.emit(f"Đã click theo tọa độ X={x}, Y={y}.")
            except Exception as exc:
                self.task_progress_changed.emit("Click theo tọa độ", "failed", 0, 1)
                self.progress_changed.emit(
                    completed + 1, max(1, total), "Lỗi: Click theo tọa độ"
                )
                self.log_message.emit(f"Không thể click tọa độ ({x}, {y}): {exc}")
