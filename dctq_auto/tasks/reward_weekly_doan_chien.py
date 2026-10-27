# Tác vụ nhận thưởng Đoàn Chiến.

import time
from pathlib import Path


def run_reward_weekly_doan_chien(self, device, completed: int, total: int) -> int:
    """Chạy luồng nhận thưởng Đoàn Chiến và trả về số tác vụ đã xử lý."""
    if self._config.get("reward_weekly_doan_chien"):
        label = "Nhận thưởng - Đoàn Chiến"
        self.task_progress_changed.emit(label, "running", 0, 1)
        try:
            if not self._wait_if_paused():
                self.log_message.emit("Đã dừng trước khi nhận thưởng Đoàn Chiến.")
                return
            import json
    
            regions_path = Path(__file__).resolve().parent / "common" / "regions.json"
            regions_data = json.loads(regions_path.read_text(encoding="utf-8"))
            # menu_chien_tranh thuộc cấu hình riêng của màn hình Chiến Tranh,
            # không nằm trong elements của Mưu Binh hoặc Giao Tranh.
            menu = regions_data["regions"]["chien_tranh"]["menu_chien_tranh"]
            bounds = menu["bounds"]
            rect = (
                int(bounds["left"]), int(bounds["top"]),
                int(bounds["right"]), int(bounds["bottom"]),
            )
            # Bước 1: OCR dùng toàn bộ tham số cấu hình trong regions.json.
            ocr_steps = tuple(menu.get("steps", ["gray", "white_text"]))
            ocr_psm = tuple(int(value) for value in menu.get("psm", [11]))
            text_color = menu.get("text_color", "#FFFFFF")
            background_color = menu.get("background_color", "#202020")
            color_tolerance = float(menu.get("color_tolerance", 38))
            detected_words = self._ocr_words_in_rect(
                device,
                rect,
                steps=ocr_steps,
                psm=ocr_psm,
                text_color=text_color,
                background_color=background_color,
                color_tolerance=color_tolerance,
            )
            detected_text = " | ".join(
                f"{word.get('text', '')} ({word.get('confidence', 0):.1f}%)"
                for word in detected_words
            ) or "<không nhận diện được từ nào>"
            self.log_message.emit(
                f"Bước 1 OCR menu_chien_tranh: RECT={rect}; text nhận diện: {detected_text}"
            )
            match = self._tap_ocr_phrase_in_rect(
                device,
                ("chien_tranh",),
                rect,
                steps=ocr_steps,
                psm=ocr_psm,
                tap=False,
                background_color=background_color,
                text_color=text_color,
                color_tolerance=color_tolerance,
            )
            if match is None:
                raise RuntimeError(
                    f"OCR không tìm thấy 'chien_tranh' trong RECT {rect}; "
                    f"text nhận diện: {detected_text}; chưa click."
                )
            center = menu["center"]
            x, y = int(center["x_px"]), int(center["y_px"])
            if x <= 1 or y <= 1:
                raise RuntimeError(
                    "Tọa độ menu_chien_tranh chưa được cấu hình trong regions.json."
                )
            device.shell(f"input tap {x} {y}")
            time.sleep(0.5)
            self.log_message.emit(
                f"Đã OCR xác nhận 'chien_tranh' trong RECT {rect}; click menu_chien_tranh tại ({x}, {y})."
            )
    
            # Bước 2: đợi màn hình Chiến Tranh tải; thử OCR tối đa 3 lần,
            # mỗi lần cách nhau 5 giây.
            screen_rect_data = regions_data["regions"]["giao_tranh"]["ocr_man_hinh_chien_tranh"]
            screen_rect = (
                int(screen_rect_data["left"]), int(screen_rect_data["top"]),
                int(screen_rect_data["right"]), int(screen_rect_data["bottom"]),
            )
            screen_found = False
            for attempt in range(1, 4):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng khi chờ màn hình Chiến Tranh.")
                    return
                if attempt > 1:
                    self.log_message.emit(
                        f"Chưa thấy 'chien_tranh' trên màn hình Chiến Tranh; "
                        f"chờ 5 giây trước lần thử {attempt}/3."
                    )
                    for _ in range(50):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng khi chờ màn hình Chiến Tranh.")
                            return
                        time.sleep(0.1)
                match = self._tap_ocr_phrase_in_rect(
                    device,
                    ("chien_tranh",),
                    screen_rect,
                    steps=("color_text",),
                    psm=(11,),
                    tap=False,
                    background_color="#000000",
                    text_color="#FFFFFF",
                    color_tolerance=30.0,
                )
                if match is not None:
                    screen_found = True
                    self.log_message.emit(
                        f"Bước 2: OCR thấy 'chien_tranh' trong RECT {screen_rect} "
                        f"(lần {attempt}/3)."
                    )
                    break
                self.log_message.emit(
                    f"Bước 2: chưa nhận diện được 'chien_tranh' "
                    f"(lần {attempt}/3)."
                )
            if not screen_found:
                raise RuntimeError(
                    f"Không tìm thấy 'chien_tranh' trong RECT {screen_rect} sau 3 lần thử."
                )
    
            # Bước 3: tìm Đoàn Chiến theo độ tương đồng OCR; nếu chưa thấy,
            # swipe danh sách tối đa 3 lần và OCR lại sau mỗi lần swipe.
            from difflib import SequenceMatcher
    
            doan_config = regions_data["regions"]["chien_tranh"]["doan_chien"]
            doan_rect_data = doan_config["ocr_rect"]
            doan_rect = (
                int(doan_rect_data["left"]), int(doan_rect_data["top"]),
                int(doan_rect_data["right"]), int(doan_rect_data["bottom"]),
            )
            doan_target = self._normalize_screen_text(
                str(doan_config.get("target_text", "doan_chien"))
            ).replace(" ", "")
            similarity_threshold = float(doan_config.get("similarity_threshold", 0.75))
            doan_steps = tuple(doan_config.get("steps", ["gray", "color_text"]))
            doan_psm = tuple(int(value) for value in doan_config.get("psm", [11]))
            doan_text_color = doan_config.get("text_color", "#D8AF67")
            doan_background_color = doan_config.get("background_color", "#74472B")
            doan_tolerance = float(doan_config.get("color_tolerance", 100))
            doan_elements = {
                item["name"]: item
                for item in regions_data["regions"]["chien_tranh"].get("elements", [])
            }
            swipe_start_name = str(doan_config.get("swipe_start", "chien_tranh_loi_vao_2"))
            swipe_end_name = str(doan_config.get("swipe_end", "chien_tranh_loi_vao_1"))
            swipe_start = doan_elements[swipe_start_name]["center"]
            swipe_end = doan_elements[swipe_end_name]["center"]
            sx, sy = int(swipe_start["x_px"]), int(swipe_start["y_px"])
            ex, ey = int(swipe_end["x_px"]), int(swipe_end["y_px"])
            max_swipes = max(0, int(doan_config.get("max_swipes", 3)))
            swipe_duration_ms = max(1, int(doan_config.get("swipe_duration_ms", 500)))
    
            doan_found = False
            for attempt in range(max_swipes + 1):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trong khi tìm mục Đoàn Chiến.")
                    return
                words = self._ocr_words_in_rect(
                    device,
                    doan_rect,
                    steps=doan_steps,
                    psm=doan_psm,
                    text_color=doan_text_color,
                    background_color=doan_background_color,
                    color_tolerance=doan_tolerance,
                )
                word_texts = [
                    str(word.get("text", "")).strip()
                    for word in words if str(word.get("text", "")).strip()
                ]
                observed_text = " ".join(word_texts)
                # Ưu tiên cụm OCR khớp trực tiếp trước khi thử so sánh
                # các cửa sổ từ liền kề.
                best_score = 0.0
                best_candidate = ""
                matched_word_indices = None
                for index, word_text in enumerate(word_texts):
                    candidate = self._normalize_screen_text(word_text).replace(" ", "")
                    score = SequenceMatcher(None, doan_target, candidate).ratio()
                    if score > best_score:
                        best_score = score
                        best_candidate = word_text
                        matched_word_indices = (index, index + 1)
    
                normalized_words = [
                    self._normalize_screen_text(text).replace(" ", "")
                    for text in word_texts
                ]
                for window_size in range(2, min(5, len(words)) + 1):
                    for begin in range(0, len(words) - window_size + 1):
                        end_index = begin + window_size
                        candidate = "".join(normalized_words[begin:end_index])
                        score = SequenceMatcher(None, doan_target, candidate).ratio()
                        if score > best_score:
                            best_score = score
                            best_candidate = " ".join(word_texts[begin:end_index])
                            matched_word_indices = (begin, end_index)
                self.log_message.emit(
                    f"Bước 3 OCR Đoàn Chiến: lần OCR {attempt + 1}/{max_swipes + 1}; "
                    f"RECT={doan_rect}; text nhận diện: {observed_text or '(trống)'}; "
                    f"độ tương đồng cao nhất={best_score:.1%}; ngưỡng >{similarity_threshold:.0%}."
                )
                if best_score > similarity_threshold:
                    doan_found = True
                    if matched_word_indices is not None:
                        begin, end_index = matched_word_indices
                        matched_words = words[begin:end_index]
                        left = min(int(word.get("left", word.get("x", 0))) for word in matched_words)
                        top = min(int(word.get("top", word.get("y", 0))) for word in matched_words)
                        right = max(
                            int(word.get("left", word.get("x", 0))) +
                            int(word.get("width", word.get("w", 0))
                            ) for word in matched_words
                        )
                        bottom = max(
                            int(word.get("top", word.get("y", 0))) +
                            int(word.get("height", word.get("h", 0))
                            ) for word in matched_words
                        )
                        width = right - left
                        height = bottom - top
                        center_x = left + width // 2
                        center_y = top + height // 2
                        self.log_message.emit(
                            f"Bước 3: tìm thấy '{doan_target}' — OCR text="
                            f"'{best_candidate}', độ tương đồng={best_score:.1%}; "
                            f"tọa độ vùng chữ ({left}; {top}; {width}; {height}), "
                            f"tâm ({center_x}; {center_y})."
                        )
                        if width > 0 and height > 0:
                            device.shell(f"input tap {center_x} {center_y}")
                            self.log_message.emit(
                                f"Bước 3: đã click mục Đoàn Chiến tại "
                                f"({center_x}; {center_y})."
                            )
                            time.sleep(0.8)
                        else:
                            raise RuntimeError(
                                "OCR khớp doan_chien nhưng kết quả không có kích thước "
                                f"tọa độ hợp lệ: {matched_word}."
                            )
                    else:
                        raise RuntimeError(
                            "OCR đạt ngưỡng doan_chien nhưng không xác định được "
                            "tọa độ từ kết quả OCR."
                        )
                    break
                if attempt < max_swipes:
                    self.log_message.emit(
                        f"Bước 3: chưa thấy 'doan_chien' đạt ngưỡng; "
                        f"swipe lần {attempt + 1}/{max_swipes} từ "
                        f"{swipe_start_name}=({sx}, {sy}) đến "
                        f"{swipe_end_name}=({ex}, {ey}), {swipe_duration_ms} ms."
                    )
                    device.shell(
                        f"input swipe {sx} {sy} {ex} {ey} {swipe_duration_ms}"
                    )
                    time.sleep(0.5)
            if not doan_found:
                raise RuntimeError(
                    f"Không tìm thấy 'doan_chien' với độ tương đồng >"
                    f"{similarity_threshold:.0%} sau {max_swipes} lần swipe; "
                    f"RECT={doan_rect}."
                )
    
            # Bước 4: xác nhận đã vào quy trình Đại chiến quân đoàn.
            # Nếu không thấy tiêu đề sau 3 lần OCR (cách nhau 3 giây),
            # kiểm tra dấu hiệu chưa báo danh và đóng màn hình báo danh nếu cần.
            from difflib import SequenceMatcher

            reward_cfg = regions_data["regions"]["reward_weekly_doan_chien"]
            flow_ocr = reward_cfg["ocr_quy_trinh_dai_chien_quan_doan"]
            flow_bounds = flow_ocr["bounds"]
            flow_rect = (
                int(flow_bounds["left"]), int(flow_bounds["top"]),
                int(flow_bounds["right"]), int(flow_bounds["bottom"]),
            )
            flow_target = self._normalize_screen_text(
                str(flow_ocr.get("target_text", "quy_trinh_dai_chien_quan_doan"))
            ).replace(" ", "")
            flow_steps = tuple(flow_ocr.get("steps", ["color_text"]))
            flow_psm = tuple(int(value) for value in flow_ocr.get("psm", [11]))
            flow_text_color = flow_ocr.get("text_color", "#FFFFFF")
            flow_background_color = flow_ocr.get("background_color", "#000000")
            flow_tolerance = float(flow_ocr.get("color_tolerance", 38))
            flow_threshold = float(flow_ocr.get("similarity_threshold", 0.90))
            flow_found = False
            for attempt in range(1, 4):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng khi xác nhận quy trình Đại chiến quân đoàn.")
                    return
                if attempt > 1:
                    self.log_message.emit(
                        f"Bước 4: chờ 3 giây trước lần OCR tiêu đề {attempt}/3."
                    )
                    for _ in range(30):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng khi chờ OCR quy trình Đại chiến quân đoàn.")
                            return
                        time.sleep(0.1)
                flow_words = self._ocr_words_in_rect(
                    device, flow_rect, steps=flow_steps, psm=flow_psm,
                    text_color=flow_text_color, background_color=flow_background_color,
                    color_tolerance=flow_tolerance,
                )
                flow_observed = "".join(
                    self._normalize_screen_text(str(word.get("text", ""))).replace(" ", "")
                    for word in flow_words
                )
                flow_score = SequenceMatcher(None, flow_target, flow_observed).ratio() if flow_observed else 0.0
                self.log_message.emit(
                    f"Bước 4 OCR tiêu đề: lần {attempt}/3; RECT={flow_rect}; "
                    f"text='{flow_observed or '(trống)'}'; tương đồng={flow_score:.1%}, "
                    f"ngưỡng ≥{flow_threshold:.0%}."
                )
                if flow_score >= flow_threshold:
                    flow_found = True
                    break

            if not flow_found:
                fallback_ocr = reward_cfg["ocr_bao_danh_doan_chien"]
                fallback_bounds = fallback_ocr["bounds"]
                fallback_rect = (
                    int(fallback_bounds["left"]), int(fallback_bounds["top"]),
                    int(fallback_bounds["right"]), int(fallback_bounds["bottom"]),
                )
                fallback_steps = tuple(fallback_ocr.get("steps", ["color_text"]))
                fallback_psm = tuple(int(value) for value in fallback_ocr.get("psm", [11]))
                fallback_text_color = fallback_ocr.get("text_color", "#FFFFFF")
                fallback_background_color = fallback_ocr.get("background_color", "#000000")
                fallback_tolerance = float(fallback_ocr.get("color_tolerance", 38))
                fallback_threshold = float(fallback_ocr.get("similarity_threshold", 0.75))
                fallback_targets = tuple(
                    self._normalize_screen_text(str(value)).replace(" ", "")
                    for value in fallback_ocr.get("target_texts", [
                        "so_thanh_vien_can_dat_30", "cap_binh_quan_quan_doan_yeu_cau_100"
                    ])
                )
                fallback_words = self._ocr_words_in_rect(
                    device, fallback_rect, steps=fallback_steps, psm=fallback_psm,
                    text_color=fallback_text_color, background_color=fallback_background_color,
                    color_tolerance=fallback_tolerance,
                )
                fallback_texts = [
                    self._normalize_screen_text(str(word.get("text", ""))).replace(" ", "")
                    for word in fallback_words if str(word.get("text", "")).strip()
                ]
                fallback_observed = "".join(fallback_texts)
                fallback_best_score = 0.0
                fallback_best_target = ""
                for target in fallback_targets:
                    candidates = [fallback_observed, *fallback_texts]
                    for size in range(2, min(6, len(fallback_texts)) + 1):
                        candidates.extend(
                            "".join(fallback_texts[start:start + size])
                            for start in range(len(fallback_texts) - size + 1)
                        )
                    for candidate in candidates:
                        score = SequenceMatcher(None, target, candidate).ratio() if candidate else 0.0
                        if score > fallback_best_score:
                            fallback_best_score = score
                            fallback_best_target = target
                self.log_message.emit(
                    f"Bước 4 OCR dự phòng báo danh: RECT={fallback_rect}; "
                    f"text='{fallback_observed or '(trống)'}'; mục khớp='{fallback_best_target or '(không có)'}'; "
                    f"tương đồng={fallback_best_score:.1%}, ngưỡng >{fallback_threshold:.0%}."
                )
                if fallback_best_score > fallback_threshold:
                    close_button = next(
                        (item for item in reward_cfg.get("elements", [])
                         if item.get("name") == "dong_man_hinh_bao_danh_doan_chien"),
                        None,
                    )
                    if close_button is None or "center" not in close_button:
                        raise RuntimeError(
                            "Thiếu tọa độ dong_man_hinh_bao_danh_doan_chien trong regions.json."
                        )
                    close_center = close_button["center"]
                    cx, cy = int(close_center["x_px"]), int(close_center["y_px"])
                    device.shell(f"input tap {cx} {cy}")
                    self.log_message.emit(
                        f"Bước 4: chưa báo danh nên chưa nhận thưởng được; OCR khớp "
                        f"'{fallback_best_target}' ({fallback_best_score:.1%}); đã click "
                        f"dong_man_hinh_bao_danh_doan_chien tại ({cx}, {cy})."
                    )
                    time.sleep(0.5)
                else:
                    self.log_message.emit(
                        "Bước 4: tiêu đề quy trình không xuất hiện sau 3 lần và OCR dự phòng "
                        "không khớp dấu hiệu chưa báo danh; tiếp tục kiểm tra bước nhận thưởng."
                    )

            # Bước 5: chờ nút nhận thưởng xuất hiện; OCR tối đa 10 lần, cách nhau 3 giây.
            reward_cfg = regions_data["regions"]["reward_weekly_doan_chien"]
            reward_ocr = reward_cfg["ocr_nhan_thuong_dai_chien_quan_doan"]
            reward_bounds = reward_ocr["bounds"]
            reward_rect = (
                int(reward_bounds["left"]), int(reward_bounds["top"]),
                int(reward_bounds["right"]), int(reward_bounds["bottom"]),
            )
            reward_target = str(reward_ocr.get("target_text", "nhan_thuong"))
            reward_steps = tuple(reward_ocr.get("steps", ["color_text"]))
            reward_psm = tuple(int(value) for value in reward_ocr.get("psm", [11]))
            reward_text_color = reward_ocr.get("text_color", "#FFFFFF")
            reward_background_color = reward_ocr.get("background_color", "#000000")
            reward_tolerance = float(reward_ocr.get("color_tolerance", 38))
            reward_threshold = float(reward_ocr.get("similarity_threshold", 0.9))
            # Bước 5: mỗi lần OCR kiểm tra cả hai trạng thái trong cùng một RECT:
            # nếu đã nhận thưởng ("da_nhan") thì thoát; nếu còn nút "nhan_thuong" thì nhận.
            exit_button = next(
                (item for item in reward_cfg.get("elements", [])
                 if item.get("name") == "thoat_man_hinh_nhan_thuong_quan_doan"),
                None,
            )
            if exit_button is None or "center" not in exit_button:
                raise RuntimeError(
                    "Thiếu tọa độ thoat_man_hinh_nhan_thuong_quan_doan trong regions.json."
                )
            exit_center = exit_button["center"]
            tx, ty = int(exit_center["x_px"]), int(exit_center["y_px"])
            already_received_target = str(reward_ocr.get("already_received_text", "da_nhan"))
            reward_found = False
            already_received = False
            for attempt in range(1, 11):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng khi chờ nút nhận thưởng Đoàn Chiến.")
                    return
                if attempt > 1:
                    self.log_message.emit(
                        f"Bước 5: chờ 3 giây trước lần OCR nhận thưởng {attempt}/10."
                    )
                    for _ in range(30):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng khi chờ nút nhận thưởng Đoàn Chiến.")
                            return
                        time.sleep(0.1)
                already_received_match = self._tap_ocr_phrase_in_rect(
                    device,
                    (already_received_target,),
                    reward_rect,
                    steps=reward_steps,
                    psm=reward_psm,
                    tap=False,
                    background_color=reward_background_color,
                    text_color=reward_text_color,
                    color_tolerance=reward_tolerance,
                )
                if already_received_match is not None:
                    device.shell(f"input tap {tx} {ty}")
                    already_received = True
                    self.log_message.emit(
                        f"Bước 5: OCR tìm thấy '{already_received_target}' trong RECT {reward_rect} "
                        f"(lần {attempt}/10); đã click thoat_man_hinh_nhan_thuong_quan_doan tại ({tx}, {ty})."
                    )
                    break
                match = self._tap_ocr_phrase_in_rect(
                    device,
                    (reward_target,),
                    reward_rect,
                    steps=reward_steps,
                    psm=reward_psm,
                    tap=False,
                    background_color=reward_background_color,
                    text_color=reward_text_color,
                    color_tolerance=reward_tolerance,
                )
                if match is not None:
                    reward_found = True
                    button = next(
                        (item for item in reward_cfg.get("elements", [])
                         if item.get("name") == "nhan_thuong_dai_chien_quan_doan"),
                        None,
                    )
                    if button is None or "center" not in button:
                        raise RuntimeError(
                            "Thiếu tọa độ nhan_thuong_dai_chien_quan_doan trong regions.json."
                        )
                    button_center = button["center"]
                    bx, by = int(button_center["x_px"]), int(button_center["y_px"])
                    device.shell(f"input tap {bx} {by}")
                    self.log_message.emit(
                        f"Bước 5: OCR tìm thấy '{reward_target}' trong RECT {reward_rect} "
                        f"(lần {attempt}/10); đã click nhan_thuong_dai_chien_quan_doan tại ({bx}, {by})."
                    )
                    break
                self.log_message.emit(
                    f"Bước 5: chưa thấy '{reward_target}' trong RECT {reward_rect} "
                    f"(lần {attempt}/10)."
                )
            if already_received:
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã nhận thưởng Đoàn Chiến; đã thoát màn hình nhận thưởng")
                return completed
            if not reward_found:
                raise RuntimeError(
                    f"Không tìm thấy '{reward_target}' hoặc '{already_received_target}' "
                    f"trong RECT {reward_rect} sau 10 lần OCR; không click."
                )
            # Bước 6: xác nhận đã nhận thưởng bằng thông báo 'ấn vào chỗ trống để thoát'.
            from difflib import SequenceMatcher
            exit_cfg = reward_cfg["ocr_an_vao_cho_trong_de_thoat"]
            exit_bounds = exit_cfg["bounds"]
            exit_rect = (
                int(exit_bounds["left"]), int(exit_bounds["top"]),
                int(exit_bounds["right"]), int(exit_bounds["bottom"]),
            )
            exit_target = self._normalize_screen_text(str(exit_cfg.get("target_text", "an_vao_cho_trong_de_thoat"))).replace(" ", "")
            exit_threshold = float(exit_cfg.get("similarity_threshold", 0.75))
            exit_steps = tuple(exit_cfg.get("steps", ["color_text"]))
            exit_psm = tuple(int(value) for value in exit_cfg.get("psm", [11]))
            exit_text_color = exit_cfg.get("text_color", "#FFFFFF")
            exit_background_color = exit_cfg.get("background_color", "#000000")
            exit_tolerance = float(exit_cfg.get("color_tolerance", 38))
            exit_found = False
            for attempt in range(1, 4):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng khi xác nhận nhận thưởng Đoàn Chiến.")
                    return
                if attempt > 1:
                    for _ in range(30):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng khi chờ xác nhận nhận thưởng Đoàn Chiến.")
                            return
                        time.sleep(0.1)
                exit_words = self._ocr_words_in_rect(
                    device, exit_rect, steps=exit_steps, psm=exit_psm,
                    text_color=exit_text_color, background_color=exit_background_color,
                    color_tolerance=exit_tolerance,
                )
                observed = "".join(
                    self._normalize_screen_text(str(word.get("text", ""))).replace(" ", "")
                    for word in exit_words
                )
                score = SequenceMatcher(None, exit_target, observed).ratio() if observed else 0.0
                self.log_message.emit(
                    f"Bước 6 OCR xác nhận: lần {attempt}/3; RECT={exit_rect}; "
                    f"text='{observed or '(trống)'}'; tương đồng={score:.1%}, ngưỡng >{exit_threshold:.0%}."
                )
                if score > exit_threshold:
                    exit_found = True
                    break
            if not exit_found:
                raise RuntimeError(
                    f"Không tìm thấy thông báo '{exit_target}' với độ tương đồng >{exit_threshold:.0%} "
                    f"trong RECT {exit_rect} sau 3 lần OCR; không thực hiện click lặp."
                )
            # Thử tối đa 5 lần: đóng màn hình chia sẻ rồi kiểm tra đã nhận thưởng.
            close_share = next(
                (item for item in reward_cfg.get("elements", [])
                 if item.get("name") == "tat_man_hinh_chia_se_nhan_thuong"),
                None,
            )
            if close_share is None or "center" not in close_share:
                raise RuntimeError("Thiếu tọa độ tat_man_hinh_chia_se_nhan_thuong trong regions.json.")
            share_center = close_share["center"]
            sx, sy = int(share_center["x_px"]), int(share_center["y_px"])

            already_target = self._normalize_screen_text(
                str(reward_cfg["ocr_nhan_thuong_dai_chien_quan_doan"].get("already_received_text", "da_nhan"))
            ).replace(" ", "")
            already_cfg = reward_cfg["ocr_nhan_thuong_dai_chien_quan_doan"]
            already_bounds = already_cfg["bounds"]
            already_rect = (
                int(already_bounds["left"]), int(already_bounds["top"]),
                int(already_bounds["right"]), int(already_bounds["bottom"]),
            )
            already_steps = tuple(already_cfg.get("steps", ["color_text"]))
            already_psm = tuple(int(value) for value in already_cfg.get("psm", [11]))
            already_text_color = already_cfg.get("text_color", "#FFFFFF")
            already_background_color = already_cfg.get("background_color", "#000000")
            already_tolerance = float(already_cfg.get("color_tolerance", 38))
            already_threshold = float(already_cfg.get("similarity_threshold", 0.75))
            received_success = False

            for attempt in range(1, 6):
                if not self._wait_if_paused():
                    self.log_message.emit("Đã dừng trong chuỗi xác nhận nhận thưởng Đoàn Chiến.")
                    return
                device.shell(f"input tap {sx} {sy}")
                self.log_message.emit(
                    f"Bước 6: lần {attempt}/5 click tat_man_hinh_chia_se_nhan_thuong tại ({sx}, {sy})."
                )
                # Chờ giao diện cập nhật sau khi click rồi OCR trạng thái đã nhận.
                for _ in range(10):
                    if not self._wait_if_paused():
                        self.log_message.emit("Đã dừng khi chờ OCR xác nhận đã nhận thưởng.")
                        return
                    time.sleep(0.1)
                already_words = self._ocr_words_in_rect(
                    device, already_rect, steps=already_steps, psm=already_psm,
                    text_color=already_text_color, background_color=already_background_color,
                    color_tolerance=already_tolerance,
                )
                already_observed = "".join(
                    self._normalize_screen_text(str(word.get("text", ""))).replace(" ", "")
                    for word in already_words
                )
                already_score = SequenceMatcher(None, already_target, already_observed).ratio() if already_observed else 0.0
                self.log_message.emit(
                    f"Bước 6 OCR xác nhận đã nhận: lần {attempt}/5; RECT={already_rect}; "
                    f"text='{already_observed or '(trống)'}'; tương đồng={already_score:.1%}, "
                    f"ngưỡng >{already_threshold:.0%}."
                )
                if already_score > already_threshold:
                    received_success = True
                    self.log_message.emit("Bước 6: xác nhận đã nhận thưởng thành công qua text 'da_nhan'.")

                    # Đóng màn hình nhận thưởng để hoàn tất tính năng.
                    exit_reward_button = next(
                        (item for item in reward_cfg.get("elements", [])
                         if item.get("name") == "thoat_man_hinh_nhan_thuong_quan_doan"),
                        None,
                    )
                    if exit_reward_button is None or "center" not in exit_reward_button:
                        raise RuntimeError(
                            "Thiếu tọa độ thoat_man_hinh_nhan_thuong_quan_doan trong regions.json."
                        )
                    exit_reward_center = exit_reward_button["center"]
                    ex, ey = int(exit_reward_center["x_px"]), int(exit_reward_center["y_px"])
                    device.shell(f"input tap {ex} {ey}")
                    self.log_message.emit(
                        f"Đã click thoat_man_hinh_nhan_thuong_quan_doan tại ({ex}, {ey}); "
                        "hoàn tất Nhận Thưởng - Quân Đoàn."
                    )
                    break
                if attempt < 5:
                    for _ in range(20):
                        if not self._wait_if_paused():
                            self.log_message.emit("Đã dừng khi chờ lần xác nhận nhận thưởng tiếp theo.")
                            return
                        time.sleep(0.1)

            if not received_success:
                raise RuntimeError(
                    f"Đã thử 5 lần click tat_man_hinh_chia_se_nhan_thuong nhưng không OCR xác nhận được "
                    f"'{already_target}' trong RECT {already_rect}."
                )
            completed += 1
            self.task_progress_changed.emit(label, "done", 1, 1)
            self.progress_changed.emit(completed, max(1, total), "Đã mở menu Chiến Tranh")
        except Exception as exc:
            self.log_message.emit(f"{label}: LỖI — {exc}")
            completed += 1
            self.task_progress_changed.emit(label, "failed", 0, 1)
            self.progress_changed.emit(completed, max(1, total), f"Lỗi: {label}")
    return completed
