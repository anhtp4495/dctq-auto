"""Tác vụ nhận thưởng Đoàn Chiến."""

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
    
                completed += 1
                self.task_progress_changed.emit(label, "done", 1, 1)
                self.progress_changed.emit(completed, max(1, total), "Đã mở menu Chiến Tranh")
            except Exception as exc:
                self.log_message.emit(f"{label}: LỖI — {exc}")
                completed += 1
                self.task_progress_changed.emit(label, "failed", 0, 1)
                self.progress_changed.emit(completed, max(1, total), f"Lỗi: {label}")
    return completed
