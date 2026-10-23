"""OCR helpers mixed into the GUI worker; orchestration stays in the GUI worker."""

import re
import unicodedata

import pytesseract
from PIL import ImageOps


class OcrWorkerMixin:
    @staticmethod
    def _normalize_screen_text(text: str) -> str:
        text = unicodedata.normalize("NFD", text.lower())
        text = "".join(
            char for char in text
            if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        return re.sub(r"[^a-z0-9]+", " ", text).strip()

    @staticmethod
    def _normalize_ocr_match_text(text: str) -> str:
        """Normalize OCR text to lowercase ASCII letters/digits only."""
        normalized = unicodedata.normalize("NFD", text.lower())
        normalized = "".join(
            char for char in normalized
            if unicodedata.category(char) != "Mn"
        ).replace("đ", "d")
        return re.sub(r"[^a-z0-9]", "", normalized)

    @staticmethod
    def _fuzzy_ocr_target_match(
        recognized_text: str,
        target_text: str,
        threshold: float = 0.25,
    ) -> bool:
        """Match a target against any OCR substring when similarity is above 25% by default."""
        from difflib import SequenceMatcher

        target = OcrWorkerMixin._normalize_ocr_match_text(target_text)
        recognized = OcrWorkerMixin._normalize_ocr_match_text(recognized_text)
        if not target or not recognized:
            return False
        if target in recognized:
            return True

        # Partial matching: OCR often appends adjacent labels/noise to the target.
        # Compare windows close to the target length so surrounding text does not
        # reduce the score of an otherwise recognizable label.
        min_len = max(1, int(len(target) * threshold))
        max_len = min(len(recognized), len(target) + max(2, int(len(target) * 0.5)))
        for window_len in range(min_len, max_len + 1):
            for start in range(0, len(recognized) - window_len + 1):
                candidate = recognized[start:start + window_len]
                score = SequenceMatcher(None, target, candidate).ratio()
                if score > threshold:
                    return True
        return False

    @staticmethod
    def _screen_text(device) -> str:
        """Read visible game text using multiple Tesseract layouts for small UI labels."""
        image = ImageOps.autocontrast(device.screenshot().convert("L"))
        recognized: list[str] = []
        for language in ("vie+eng", "eng"):
            language_failed = False
            for page_mode in (6, 11):
                try:
                    text = pytesseract.image_to_string(
                        image, lang=language, config=f"--psm {page_mode}"
                    ).strip()
                except pytesseract.TesseractError:
                    language_failed = True
                    break
                if text and text not in recognized:
                    recognized.append(text)
            if not language_failed and recognized:
                break
        # Combine layout passes so a label missed by block-oriented OCR can still
        # contribute to the conservative login-screen checks.
        return "\\n".join(recognized)

    @staticmethod
    def _screen_text_in_rect(device, rect: tuple[int, int, int, int]) -> str:
        """OCR only the supplied (left, top, right, bottom) screenshot rectangle."""
        left, top, right, bottom = rect
        image = device.screenshot().convert("RGB")
        width, height = image.size
        left = max(0, min(int(left), width - 1))
        top = max(0, min(int(top), height - 1))
        right = max(left + 1, min(int(right), width))
        bottom = max(top + 1, min(int(bottom), height))
        cropped = ImageOps.autocontrast(image.crop((left, top, right, bottom)).convert("L"))
        recognized: list[str] = []
        for language in ("vie+eng", "eng"):
            language_failed = False
            for page_mode in (6, 11):
                try:
                    text = pytesseract.image_to_string(
                        cropped, lang=language, config=f"--psm {page_mode}"
                    ).strip()
                except pytesseract.TesseractError:
                    language_failed = True
                    break
                if text and text not in recognized:
                    recognized.append(text)
            if not language_failed and recognized:
                break
        return "\\n".join(recognized)

    @staticmethod
    def _tap_ocr_word(device, words: tuple[str, ...]) -> bool:
        """Tap a live OCR word or phrase, including labels split into multiple words."""
        image = ImageOps.autocontrast(device.screenshot().convert("L"))
        try:
            data = pytesseract.image_to_data(
                image, lang="vie+eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                image, lang="eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )

        wanted = {OcrWorkerMixin._normalize_screen_text(word) for word in words}
        candidates = []
        lines = {}
        total_words = len(data.get("text", []))
        blocks = data.get("block_num", [0] * total_words)
        paragraphs = data.get("par_num", [0] * total_words)
        line_numbers = data.get("line_num", [0] * total_words)
        for i, raw in enumerate(data.get("text", [])):
            normalized = OcrWorkerMixin._normalize_screen_text(raw)
            if not normalized:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            left, top = int(data["left"][i]), int(data["top"][i])
            width, height = int(data["width"][i]), int(data["height"][i])
            candidates.append((confidence, left, top, width, height, normalized))
            line_key = (blocks[i], paragraphs[i], line_numbers[i])
            lines.setdefault(line_key, []).append(
                (left, top, width, height, confidence, normalized)
            )

        matches = [
            (confidence, left, top, width, height)
            for confidence, left, top, width, height, normalized in candidates
            if normalized in wanted
        ]
        # OCR commonly splits Vietnamese labels such as "Điểm danh" into two words.
        for line_words in lines.values():
            line_words.sort(key=lambda item: item[0])
            for start_index in range(len(line_words)):
                phrase_parts = []
                for end_index in range(start_index, min(len(line_words), start_index + 5)):
                    phrase_parts.append(line_words[end_index][5])
                    if " ".join(phrase_parts) not in wanted:
                        continue
                    selected = line_words[start_index:end_index + 1]
                    left = min(item[0] for item in selected)
                    top = min(item[1] for item in selected)
                    right = max(item[0] + item[2] for item in selected)
                    bottom = max(item[1] + item[3] for item in selected)
                    confidence = sum(item[4] for item in selected) / len(selected)
                    matches.append((confidence, left, top, right - left, bottom - top))

        if not matches:
            return False
        confidence, left, top, width, height = max(matches, key=lambda item: item[0])
        x, y = int(left + width / 2), int(top + height / 2)
        device.shell(f"input tap {x} {y}")
        return True

    @staticmethod
    def _ocr_words_in_rect(
        device,
        rect: tuple[int, int, int, int],
        steps: tuple[str, ...] = ("gray", "white_text"),
        psm: tuple[int, ...] = (11,),
    ) -> list[dict]:
        """OCR a screenshot rectangle using the selected preprocessing steps and PSMs."""
        import cv2
        import numpy as np

        image = device.screenshot().convert("RGB")
        screen_width, screen_height = image.size
        left, top, right, bottom = rect
        left = max(0, min(screen_width - 1, int(left)))
        top = max(0, min(screen_height - 1, int(top)))
        right = max(left + 1, min(screen_width, int(right)))
        bottom = max(top + 1, min(screen_height, int(bottom)))
        crop_rgb = np.array(image.crop((left, top, right, bottom)))
        crop_bgr = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR)
        crop_height, crop_width = crop_bgr.shape[:2]
        scale = 3
        variants = {}

        if "gray" in steps:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(
                gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4
            )
            variants["gray"] = cv2.copyMakeBorder(
                gray, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255
            )

        if "white_text" in steps:
            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            white_mask = cv2.inRange(
                hsv,
                np.array([0, 0, 135], dtype=np.uint8),
                np.array([180, 120, 255], dtype=np.uint8),
            )
            white_mask = cv2.resize(
                white_mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST
            )
            white_mask = cv2.copyMakeBorder(
                white_mask, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=0
            )
            variants["white_text"] = cv2.bitwise_not(white_mask)

        words = []
        for variant_name, processed in variants.items():
            for page_mode in psm:
                data = None
                for language in ("vie+eng", "eng"):
                    try:
                        data = pytesseract.image_to_data(
                            processed,
                            lang=language,
                            config=f"--oem 3 --psm {page_mode}",
                            output_type=pytesseract.Output.DICT,
                        )
                        break
                    except pytesseract.TesseractError:
                        continue
                if data is None:
                    continue

                count = len(data.get("text", []))
                blocks = data.get("block_num", [0] * count)
                paragraphs = data.get("par_num", [0] * count)
                line_numbers = data.get("line_num", [0] * count)
                for i, raw in enumerate(data.get("text", [])):
                    normalized = OcrWorkerMixin._normalize_screen_text(raw)
                    if not normalized:
                        continue
                    try:
                        confidence = float(data["conf"][i])
                    except (ValueError, TypeError):
                        confidence = 0.0
                    if confidence < 0:
                        continue

                    # Reverse the scale and 18px padding used by ocr_debug.py.
                    x0 = max(0, (int(data["left"][i]) - 18) / scale)
                    y0 = max(0, (int(data["top"][i]) - 18) / scale)
                    x1 = min(crop_width, (int(data["left"][i]) + int(data["width"][i]) - 18) / scale)
                    y1 = min(crop_height, (int(data["top"][i]) + int(data["height"][i]) - 18) / scale)
                    if x1 <= x0 or y1 <= y0:
                        continue
                    words.append({
                        "text": normalized,
                        "confidence": confidence,
                        "left": left + round(x0),
                        "top": top + round(y0),
                        "width": max(1, round(x1) - round(x0)),
                        "height": max(1, round(y1) - round(y0)),
                        "line_key": (variant_name, page_mode, blocks[i], paragraphs[i], line_numbers[i]),
                    })
        return words

    @staticmethod
    def _tap_ocr_phrase_in_rect(
        device,
        words: tuple[str, ...],
        rect: tuple[int, int, int, int],
        steps: tuple[str, ...] = ("gray", "white_text"),
        psm: tuple[int, ...] = (11,),
    ) -> tuple[int, int, tuple[int, int, int, int]] | None:
        """Find and tap a word or contiguous phrase; return tap point and detected rectangle."""
        wanted = {OcrWorkerMixin._normalize_screen_text(word) for word in words}
        detected = OcrWorkerMixin._ocr_words_in_rect(device, rect, steps=steps, psm=psm)
        matches = [word for word in detected if word["text"] in wanted]

        # OCR often separates Vietnamese labels into adjacent words on the same line.
        lines = {}
        for word in detected:
            lines.setdefault(word["line_key"], []).append(word)
        for line in lines.values():
            line.sort(key=lambda item: item["left"])
            for start in range(len(line)):
                phrase_parts = []
                for end in range(start, min(len(line), start + 4)):
                    phrase_parts.append(line[end]["text"])
                    phrase = " ".join(phrase_parts)
                    if phrase not in wanted:
                        continue
                    group = line[start:end + 1]
                    x1 = min(item["left"] for item in group)
                    y1 = min(item["top"] for item in group)
                    x2 = max(item["left"] + item["width"] for item in group)
                    y2 = max(item["top"] + item["height"] for item in group)
                    matches.append({
                        "text": phrase,
                        "confidence": sum(item["confidence"] for item in group) / len(group),
                        "left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1,
                    })
        if not matches:
            return None
        match = max(matches, key=lambda item: (item["confidence"], item["width"]))
        x = match["left"] + match["width"] // 2
        y = match["top"] + match["height"] // 2
        detected_rect = (
            int(match["left"]),
            int(match["top"]),
            int(match["left"] + match["width"]),
            int(match["top"] + match["height"]),
        )
        device.shell(f"input tap {x} {y}")
        return x, y, detected_rect

    def _tap_fuzzy_ocr_target(
        self, device, target_text: str, threshold: float = 0.25,
        *, tap: bool = True,
    ) -> tuple[int, int] | None:
        """Find the best OCR word-window for a target; optionally tap its center."""
        from difflib import SequenceMatcher

        image = ImageOps.autocontrast(device.screenshot().convert("L"))
        try:
            data = pytesseract.image_to_data(
                image, lang="vie+eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                image, lang="eng", config="--psm 11",
                output_type=pytesseract.Output.DICT,
            )

        target = self._normalize_ocr_match_text(target_text)
        if not target:
            return None
        count = len(data.get("text", []))
        lines = {}
        for i, raw in enumerate(data.get("text", [])):
            normalized = self._normalize_ocr_match_text(raw)
            if not normalized:
                continue
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError):
                confidence = 0.0
            if confidence < 0:
                continue
            key = (
                data.get("block_num", [0] * count)[i],
                data.get("par_num", [0] * count)[i],
                data.get("line_num", [0] * count)[i],
            )
            lines.setdefault(key, []).append((
                int(data["left"][i]), int(data["top"][i]),
                int(data["width"][i]), int(data["height"][i]),
                confidence, normalized,
            ))

        best = None
        for line in lines.values():
            line.sort(key=lambda item: item[0])
            for start in range(len(line)):
                parts = []
                for end in range(start, min(len(line), start + 12)):
                    parts.append(line[end][5])
                    candidate = "".join(parts)
                    score = SequenceMatcher(None, target, candidate).ratio()
                    if score > threshold and (best is None or score > best[0]):
                        group = line[start:end + 1]
                        left = min(item[0] for item in group)
                        top = min(item[1] for item in group)
                        right = max(item[0] + item[2] for item in group)
                        bottom = max(item[1] + item[3] for item in group)
                        best = (score, left, top, right, bottom)
        if best is None:
            return None
        _score, left, top, right, bottom = best
        x, y = round((left + right) / 2), round((top + bottom) / 2)
        if tap:
            device.shell(f"input tap {x} {y}")
        return x, y
