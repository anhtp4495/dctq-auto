"""Worker handlers for strategy/reward tasks."""

import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract


class StrategyWorkerMixin:
    @staticmethod
    def _strategy_regions():
        """Load Mưu Binh coordinates from regions.json and reject placeholders."""
        import json

        path = Path(__file__).resolve().parents[1] / "common" / "regions.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Không đọc được regions.json: {exc}") from exc
        section = data.get("regions", {}).get("muu_binh", {})
        elements = {
            item.get("name"): item
            for item in section.get("elements", [])
            if isinstance(item, dict) and item.get("name")
        }
        return path, elements

    @staticmethod
    def _strategy_point(elements, name):
        item = elements.get(name, {})
        center = item.get("center", {})
        x, y = center.get("x_px"), center.get("y_px")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        if (int(x), int(y)) == (1, 1) or int(x) < 2 or int(y) < 2:
            return None
        return int(x), int(y)

    @staticmethod
    def _strategy_rect(elements, name):
        item = elements.get(name, {})
        bounds = item.get("bounds", {})
        try:
            left, top, right, bottom = (
                int(bounds["left"]), int(bounds["top"]),
                int(bounds["right"]), int(bounds["bottom"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if left < 0 or top < 0 or right <= left or bottom <= top:
            return None
        if (left, top, right, bottom) == (1, 1, 1, 1):
            return None
        if right - left < 5 or bottom - top < 5:
            return None
        return left, top, right, bottom

    @staticmethod
    def _read_strategy_stage_rect(device, rect: tuple[int, int, int, int]) -> tuple[str, int]:
        """OCR stage text from Rect(x, y, w, h) using the validated AI-label pipeline."""
        x, y, width, height = (int(value) for value in rect)
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            return "", -1

        screenshot = device.screenshot().convert("RGB")
        image_width, image_height = screenshot.size
        x = min(x, image_width - 1)
        y = min(y, image_height - 1)
        right = min(x + width, image_width)
        bottom = min(y + height, image_height)
        if right <= x or bottom <= y:
            return "", -1

        crop = np.asarray(screenshot.crop((x, y, right, bottom)))
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        scaled = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        try:
            raw_text = pytesseract.image_to_string(
                scaled,
                lang="eng",
                config="--oem 3 --psm 8 -c tessedit_char_whitelist=AIai0123456789",
            ).strip()
        except pytesseract.TesseractError:
            return "", -1

        compact = re.sub(r"\\s+", "", raw_text).lower()
        match = re.fullmatch(r"ai(\\d{1,3})", compact)
        if not match:
            # Permit a digit-only result if OCR omits the "Ai" prefix entirely.
            match = re.fullmatch(r"(\\d{1,3})", compact)
        if match:
            candidate = int(match.group(1))
            if 1 <= candidate <= 100:
                return raw_text, candidate
        return raw_text, -1

    def _detect_strategy_status(
        self, device, elements, log_result=True, last_known_stage=-1
    ):
        """Detect Mưu Binh state from stage OCR and three independent text OCRs."""
        # OCR 1: current stage. Keep the caller's last known stage if this read fails.
        raw_stage = ""
        stage = -1
        stage_bounds = self._strategy_rect(elements, "ai_hien_tai")
        if stage_bounds is not None:
            left, top, right, bottom = stage_bounds
            raw_stage, stage = self._read_strategy_stage_rect(
                device, (left, top, right - left, bottom - top)
            )
        remembered_stage = stage if stage > 0 else last_known_stage

        # OCR 2: one region can contain either "bat_dau" or "tro_ve".
        # OCR 3: "hoi_thanh".
        # OCR 4: "nhan_thuong".
        def read_text_region(name):
            rect = self._strategy_rect(elements, name)
            if rect is None:
                return ""
            try:
                return self._screen_text_in_rect(device, rect)
            except Exception as exc:
                if log_result:
                    self.log_message.emit(f"OCR {name} thất bại: {exc}")
                return ""

        raw_start_return = read_text_region("bat_dau_tro_ve")
        raw_hall = read_text_region("hoi_thanh")
        raw_reward = read_text_region("nhan_thuong")
        start_return = self._normalize_ocr_match_text(raw_start_return)
        hall = self._normalize_ocr_match_text(raw_hall)
        reward = self._normalize_ocr_match_text(raw_reward)

        has_start = "batdau" in start_return
        has_return = "trove" in start_return
        has_hall = "hoithanh" in hall
        has_reward = "nhanthuong" in reward

        if has_reward:
            status = "cho_nhan_thuong"
        elif has_return:
            status = "dang_chien_dau"
        elif has_start and has_hall:
            status = "cho_chien_dau"
        elif stage <= 0 and not has_start and not has_return and not has_hall and not has_reward:
            status = (
                "hoan_thanh_muu_binh"
                if remembered_stage == 100
                else "that_bai_muu_binh"
            )
        else:
            status = "khong_xac_dinh"

        if log_result:
            if stage > 0:
                self.log_message.emit(
                    f"Đã phát hiện ải hiện tại: {stage}/100 (OCR: {raw_stage or '(trống)'})."
                )
            else:
                self.log_message.emit(
                    f"Không nhận diện được ải ở lần OCR này; ải đang lưu: "
                    f"{remembered_stage if remembered_stage > 0 else 'chưa có'} "
                    f"(OCR: {raw_stage or '(trống)'})."
                )
            self.log_message.emit(
                "OCR trạng thái Mưu Binh: "
                f"bat_dau/tro_ve='{raw_start_return or '(trống)'}', "
                f"hoi_thanh='{raw_hall or '(trống)'}', "
                f"nhan_thuong='{raw_reward or '(trống)'}'; kết quả={status}."
            )
        return status, stage

    def _run_strategy_reward(self, device, elements=None):
        """Claim one random Mưu Binh reward using its configured click point."""
        import random

        if elements is None:
            _regions_path, elements = self._strategy_regions()
        candidates = [
            (name, self._strategy_point(elements, name))
            for name in ("phan_thuong_1", "phan_thuong_2", "phan_thuong_3")
        ]
        candidates = [(name, point) for name, point in candidates if point is not None]
        if not candidates:
            self.log_message.emit(
                "Nhận thưởng Mưu Binh thất bại: các tọa độ phan_thuong_1/2/3 "
                "chưa được cập nhật khỏi placeholder (1, 1)."
            )
            return False
        name, (x, y) = random.choice(candidates)
        try:
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi nhận thưởng Mưu Binh.")
                return False
            device.shell(f"input tap {x} {y}")
            self.log_message.emit(
                f"Nhận thưởng Mưu Binh: chọn ngẫu nhiên {name}, click ({x}, {y})."
            )
            time.sleep(1)
            return True
        except Exception as exc:
            self.log_message.emit(f"Nhận thưởng Mưu Binh thất bại: {exc}")
            return False

    def _run_strategy_vuot_ai(self, device):
        """Run the Vượt Ải state loop; reward handling must be explicitly selected."""
        import time as _time

        _regions_path, elements = self._strategy_regions()
        button = self._strategy_point(elements, "button_vuot_ai")
        if button is None:
            self.log_message.emit(
                "Vượt Ải thất bại: tọa độ button_vuot_ai chưa được cập nhật khỏi placeholder."
            )
            return False
        consecutive_failures = 0
        battle_started = None
        reward_clicked = False
        current_stage = -1

        try:
            while True:
                if not self._wait_if_paused():
                    self.log_message.emit("Vượt Ải đã dừng theo yêu cầu.")
                    return False

                self.log_message.emit(
                    f"Vượt Ải: click nút Vượt Ải tại ({button[0]}, {button[1]})."
                )
                device.shell(f"input tap {button[0]} {button[1]}")
                consecutive_failures = consecutive_failures
                battle_started = None
                reward_clicked = False

                while True:
                    if not self._wait_if_paused():
                        self.log_message.emit("Vượt Ải đã dừng theo yêu cầu.")
                        return False
                    try:
                        status, stage = self._detect_strategy_status(
                            device, elements, log_result=False,
                            last_known_stage=current_stage,
                        )
                    except Exception as exc:
                        self.log_message.emit(f"Vượt Ải thất bại khi phát hiện trạng thái: {exc}")
                        return False

                    if stage > 0:
                        # After claiming a reward, do not roll back the stage
                        # counter if the UI briefly still shows the previous stage.
                        if not (reward_clicked and stage < current_stage):
                            current_stage = stage
                    if status == "hoan_thanh_muu_binh":
                        self.log_message.emit(
                            f"Mưu Binh hoàn thành: ải đang lưu là {current_stage}/100 "
                            "và cả 4 OCR đều không nhận diện được."
                        )
                        return True
                    if status == "that_bai_muu_binh":
                        self.log_message.emit(
                            f"Vượt Ải thất bại: cả 4 OCR đều không nhận diện được "
                            f"nhưng ải đang lưu là {current_stage if current_stage > 0 else 'không xác định'}, "
                            "khác 100."
                        )
                        return False
                    if status == "dang_chien_dau":
                        if battle_started is None:
                            battle_started = _time.monotonic()
                        if current_stage > 0:
                            self.log_message.emit(f"Đang vượt ải {current_stage}/100")
                        else:
                            self.log_message.emit(
                                "Đang chiến đấu — chưa xác định được ải hiện tại"
                            )
                        consecutive_failures = 0
                        if _time.monotonic() - battle_started >= 180:
                            self.log_message.emit(
                                "Vượt Ải thất bại: chiến đấu quá 3 phút; yêu cầu thoát Mưu Binh."
                            )
                            self._try_close_strategy(device, elements)
                            return False
                        if not self._strategy_wait(15):
                            self.log_message.emit("Vượt Ải đã dừng theo yêu cầu.")
                            return False
                        continue

                    if status == "cho_nhan_thuong":
                        if not self._config.get("task_receive_strategy_reward"):
                            self.log_message.emit(
                                "Vượt Ải thất bại: trạng thái cho_nhan_thuong nhưng "
                                "chưa tích chọn 'Nhận thưởng Mưu Binh' trong tab Tác Vụ. "
                                "Dừng xử lý Vượt Ải."
                            )
                            return False
                        if reward_clicked:
                            self.log_message.emit(
                                "Vượt Ải thất bại: đã gọi nhận thưởng nhưng trạng thái "
                                "cho_nhan_thuong vẫn còn; dừng để tránh click lặp."
                            )
                            return False
                        if not self._run_strategy_reward(device, elements):
                            self.log_message.emit(
                                "Vượt Ải thất bại do chức năng Nhận thưởng Mưu Binh thất bại; "
                                "dừng xử lý."
                            )
                            return False
                        reward_clicked = True
                        if current_stage > 0:
                            current_stage = min(current_stage + 1, 100)
                            self.log_message.emit(
                                f"Đã nhận thưởng thành công; cập nhật ải kế tiếp: "
                                f"{current_stage}/100."
                            )
                        else:
                            self.log_message.emit(
                                "Đã nhận thưởng nhưng chưa có số ải để tăng biến theo dõi."
                            )
                        if not self._strategy_wait(2):
                            return False
                        continue

                    if status in ("chuan_bi", "cho_chien_dau"):
                        if battle_started is not None or reward_clicked:
                            consecutive_failures += 1
                        else:
                            consecutive_failures += 1
                        if consecutive_failures >= 3:
                            self.log_message.emit(
                                "Vượt Ải thất bại 3 lần liên tiếp; yêu cầu thoát Mưu Binh."
                            )
                            self._try_close_strategy(device, elements)
                            return False
                        self.log_message.emit(
                            f"Vượt Ải chưa thành công (lần thất bại liên tiếp "
                            f"{consecutive_failures}/3); sẽ thử lại."
                        )
                        break

                    self.log_message.emit(
                        "Vượt Ải dừng an toàn: không xác định được trạng thái Mưu Binh; "
                        "không tự suy đoán thắng/thua."
                    )
                    return False
        except Exception as exc:
            self.log_message.emit(f"Vượt Ải gặp lỗi: {exc}")
            return False

    def _strategy_wait(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not self._wait_if_paused():
                return False
            time.sleep(min(0.25, max(0.01, deadline - time.monotonic())))
        return True

    def _try_close_strategy(self, device, elements):
        point = self._strategy_point(elements, "close_muu_binh")
        if point is None:
            self.log_message.emit(
                "Không thể tự thoát Mưu Binh: close_muu_binh vẫn là placeholder."
            )
            return False
        try:
            device.shell(f"input tap {point[0]} {point[1]}")
            self.log_message.emit(
                f"Đã click thoát màn hình Mưu Binh tại ({point[0]}, {point[1]})."
            )
            return True
        except Exception as exc:
            self.log_message.emit(f"Không thể thoát màn hình Mưu Binh: {exc}")
            return False
