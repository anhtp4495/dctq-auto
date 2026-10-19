"""Dialog chụp màn hình ADB và đánh dấu tọa độ trên ảnh gốc."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image
import pytesseract

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.adb.client import AdbClient


LOCATIONS_PATH = Path("dctq_auto/tasks/clone/locations.json")
REGIONS_PATH = Path("dctq_auto/tasks/clone/regions.json")
SCREENSHOT_DIR = Path("artifacts/screenshots")


class ClickableImage(QWidget):
    """Show a screenshot and support point clicks or drag-to-select rectangles."""

    def __init__(
        self,
        pixmap: QPixmap,
        on_image_click,
        is_region_mode,
        on_image_rect,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self._on_image_click = on_image_click
        self._is_region_mode = is_region_mode
        self._on_image_rect = on_image_rect
        self._points: list[tuple[int, int, str]] = []
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)

    def set_points(self, points: list[tuple[int, int, str]]) -> None:
        self._points = list(points)
        self.update()

    def _target_rect(self):
        source = self._pixmap.size()
        fitted = source.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = (self.width() - fitted.width()) // 2
        y = (self.height() - fitted.height()) // 2
        from PySide6.QtCore import QRect
        return QRect(x, y, fitted.width(), fitted.height())

    def _to_image_point(self, point: QPoint) -> tuple[int, int]:
        target = self._target_rect()
        x = round((point.x() - target.x()) * self._pixmap.width() / target.width())
        y = round((point.y() - target.y()) * self._pixmap.height() / target.height())
        return (
            min(self._pixmap.width() - 1, max(0, x)),
            min(self._pixmap.height() - 1, max(0, y)),
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        target = self._target_rect()
        if not self._pixmap.isNull():
            painter.drawPixmap(target, self._pixmap)
        if not self._pixmap.isNull() and self._points:
            scale_x = target.width() / self._pixmap.width()
            scale_y = target.height() / self._pixmap.height()
            pen = QPen(Qt.GlobalColor.green)
            pen.setWidth(2)
            painter.setPen(pen)
            for index, (x, y, label) in enumerate(self._points, start=1):
                px = target.x() + round(x * scale_x)
                py = target.y() + round(y * scale_y)
                painter.drawEllipse(QPoint(px, py), 5, 5)
                painter.drawText(px + 7, py - 7, f"{index}. {label}")

            if len(self._points) == 4:
                polygon = [
                    QPoint(target.x() + round(x * scale_x), target.y() + round(y * scale_y))
                    for x, y, _label in self._points
                ]
                for index in range(4):
                    painter.drawLine(polygon[index], polygon[(index + 1) % 4])

        if self._drag_start is not None and self._drag_current is not None:
            pen = QPen(Qt.GlobalColor.yellow)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            from PySide6.QtCore import QRect
            painter.drawRect(QRect(self._drag_start, self._drag_current).normalized())

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap.isNull():
            return
        target = self._target_rect()
        point = event.position().toPoint()
        if not target.contains(point):
            return
        if self._is_region_mode():
            self._drag_start = point
            self._drag_current = point
            self.update()
            return
        x, y = self._to_image_point(point)
        self._on_image_click(x, y)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None:
            point = event.position().toPoint()
            target = self._target_rect()
            x = min(max(point.x(), target.left()), target.right())
            y = min(max(point.y(), target.top()), target.bottom())
            self._drag_current = QPoint(x, y)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            return
        start = self._drag_start
        end = self._drag_current or event.position().toPoint()
        self._drag_start = None
        self._drag_current = None
        self.update()
        x1, y1 = self._to_image_point(start)
        x2, y2 = self._to_image_point(end)
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        if right - left < 2 or bottom - top < 2:
            return
        self._on_image_rect(left, top, right, bottom)


class ScreenshotAnnotator(QDialog):
    """Capture an ADB screenshot and save point/region coordinates from that image."""

    def __init__(
        self, serial: str | None, parent=None, on_ocr_result=None, on_location_result=None
    ) -> None:
        super().__init__(parent)
        self._on_ocr_result = on_ocr_result
        self._on_location_result = on_location_result
        self.serial = serial
        self.capture_desktop = serial is None
        self.setWindowTitle(
            "Chụp màn hình hiện tại và chọn tọa độ"
            if self.capture_desktop
            else "Chụp màn hình LDPlayer và chọn tọa độ"
        )
        self.resize(1050, 760)
        self._image_path: Path | None = None
        self._pixmap = QPixmap()
        self._points: list[tuple[int, int, str]] = []
        self._on_location_result = on_location_result

        root = QVBoxLayout(self)
        heading = QLabel(
            "Chọn trực tiếp trên ảnh chụp. Tọa độ được tính theo pixel của ảnh gốc, "
            "không phụ thuộc kích thước cửa sổ xem ảnh."
            if self.capture_desktop
            else "Chọn trực tiếp trên ảnh chụp ADB. Tọa độ được tính theo pixel của ảnh gốc, "
                 "không phụ thuộc kích thước cửa sổ xem ảnh."
        )
        heading.setWordWrap(True)
        root.addWidget(heading)

        toolbar = QHBoxLayout()
        self.capture_button = QPushButton("Chụp lại màn hình")
        self.capture_button.clicked.connect(self.capture_screenshot)
        toolbar.addWidget(self.capture_button)
        self.image_info = QLabel("Chưa có ảnh.")
        self.image_info.setWordWrap(True)
        toolbar.addWidget(self.image_info, 1)
        root.addLayout(toolbar)

        settings = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Từng điểm", "RECT"])
        self.mode_combo.setToolTip("Từng điểm: nhấp để đặt tọa độ. RECT: kéo chuột để chọn hình chữ nhật.")
        settings.addRow("Chế độ chọn:", self.mode_combo)
        self.screen_name = QLineEdit("captured")
        self.screen_name.setToolTip("Tên màn hình lưu trong locations.json")
        self.ocr_text = QLineEdit()
        self.ocr_text.setPlaceholderText("Text OCR nhận diện được...")
        self.normalized_text = QLineEdit()
        self.normalized_text.setPlaceholderText("dang_nhap")
        self.ocr_text.textChanged.connect(self._update_normalized_text)
        self.ocr_item_count = QSpinBox()
        self.ocr_item_count.setRange(1, 12)
        self.ocr_item_count.setValue(3)
        self.ocr_item_count.setToolTip("Số text độc lập cần tách khi các mục nằm cùng một hàng.")
        self.ocr_items = QPlainTextEdit()
        self.ocr_items.setPlaceholderText("Mỗi dòng là một text độc lập...")
        self.ocr_items.setMaximumHeight(76)
        self.normalized_items = QPlainTextEdit()
        self.normalized_items.setPlaceholderText("moi_dong_la_mot_ten")
        self.normalized_items.setMaximumHeight(76)
        self.ocr_locations = QPlainTextEdit()
        self.ocr_locations.setReadOnly(True)
        self.ocr_locations.setPlaceholderText("Tọa độ 4 góc và trung điểm của từng text OCR")
        self.ocr_locations.setMaximumHeight(110)
        self._ocr_elements: list[dict] = []
        settings.addRow("Tên màn hình:", self.screen_name)
        settings.addRow("Text OCR (gộp):", self.ocr_text)
        settings.addRow("Tên không dấu:", self.normalized_text)
        settings.addRow("Số text cần tách:", self.ocr_item_count)
        settings.addRow("Các text độc lập:", self.ocr_items)
        settings.addRow("Tên chuẩn hóa từng text:", self.normalized_items)
        settings.addRow("Location từng text:", self.ocr_locations)
        root.addLayout(settings)

        self.instruction = QLabel("Chụp màn hình để bắt đầu.")
        self.instruction.setWordWrap(True)
        root.addWidget(self.instruction)

        self.image_view = ClickableImage(
            QPixmap(),
            self._on_image_click,
            lambda: self.mode_combo.currentText() == "RECT",
            self._on_image_rect_selected,
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_view)
        root.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        self.undo_button = QPushButton("Bỏ điểm cuối")
        self.undo_button.clicked.connect(self.undo_point)
        bottom.addWidget(self.undo_button)
        self.ocr_button = QPushButton("Nhận diện text (OCR)")
        self.ocr_button.clicked.connect(self.recognize_text)
        bottom.addWidget(self.ocr_button)
        self.clear_button = QPushButton("Xóa điểm đã chọn")
        self.clear_button.clicked.connect(self.clear_points)
        bottom.addWidget(self.clear_button)
        self.save_button = QPushButton("Lưu tọa độ")
        self.save_button.clicked.connect(self.save_coordinates)
        bottom.addWidget(self.save_button)
        bottom.addStretch(1)
        self.close_button = QPushButton("Đóng")
        self.close_button.clicked.connect(self.accept)
        bottom.addWidget(self.close_button)
        root.addLayout(bottom)

        self.capture_screenshot()

    def capture_screenshot(self) -> None:
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.capture_desktop:
                screen = QGuiApplication.primaryScreen()
                if screen is None:
                    raise RuntimeError("Không tìm thấy màn hình desktop.")
                self._image_path = SCREENSHOT_DIR / f"desktop_{timestamp}.png"
                if not screen.grabWindow(0).save(str(self._image_path), "PNG"):
                    raise RuntimeError("Không lưu được ảnh chụp desktop.")
            else:
                device = AdbClient(self.serial).connect()
                safe_serial = self.serial.replace(":", "_").replace("/", "_").replace("\\", "_")
                self._image_path = SCREENSHOT_DIR / f"{safe_serial}_{timestamp}.png"
                device.screenshot().save(str(self._image_path))
            self._pixmap = QPixmap(str(self._image_path))
            if self._pixmap.isNull():
                raise RuntimeError("Không mở được ảnh screenshot vừa chụp.")
            self._points.clear()
            self.image_view._pixmap = self._pixmap
            self.image_view.set_points(self._points)
            self.image_info.setText(
                f"{self._image_path} — ảnh gốc {self._pixmap.width()}×{self._pixmap.height()} px"
            )
            self.instruction.setText(
                "Nhấp vào vị trí trên ảnh rồi nhập text/tên cho điểm đó. "
                "OCR sẽ phân tích toàn bộ ảnh; kết quả và tọa độ được ghi vào nhật ký cửa sổ chính."
            )
            self.image_view.update()
        except Exception as exc:
            QMessageBox.critical(self, "Không chụp được màn hình", str(exc))

    def _on_image_click(self, x: int, y: int) -> None:
        if self._pixmap.isNull():
            return
        text, accepted = QInputDialog.getText(
            self, "Đặt tên tọa độ", "Nhập text/nút tại vị trí này (ví dụ: Đăng nhập):",
            text="",
        )
        if not accepted:
            return
        text = text.strip()
        if not text:
            QMessageBox.warning(self, "Thiếu text", "Hãy nhập text hoặc tên cho tọa độ.")
            return
        label = self.normalize_text(text) or text
        self._points.append((x, y, label))
        self.image_view.set_points(self._points)
        ratio_x = x / self._pixmap.width()
        ratio_y = y / self._pixmap.height()
        message = (
            f"Đã chọn tọa độ: {text} -> {label}; pixel=({x}, {y}); "
            f"ratio=({ratio_x:.6f}, {ratio_y:.6f})"
        )
        self.instruction.setText(message)
        if self._on_location_result is not None:
            self._on_location_result(text, label, x, y, ratio_x, ratio_y)

    def _on_image_rect_selected(self, left: int, top: int, right: int, bottom: int) -> None:
        """Select a named rectangle and represent its four corners as saved coordinates."""
        text, accepted = QInputDialog.getText(
            self, "Đặt tên RECT", "Nhập text/tên cho vùng chữ nhật:"
        )
        if not accepted:
            return
        name = self.normalize_text(text) or "rect"
        self._points = [
            (left, top, f"{name}_top_left"),
            (right, top, f"{name}_top_right"),
            (right, bottom, f"{name}_bottom_right"),
            (left, bottom, f"{name}_bottom_left"),
        ]
        self.image_view.set_points(self._points)
        self.instruction.setText(
            f"Đã chọn RECT '{name}': trái={left}, trên={top}, phải={right}, dưới={bottom}."
        )
        if self._on_location_result is not None:
            width, height = self._pixmap.width(), self._pixmap.height()
            self._on_location_result(
                f"RECT {text.strip()}", name, left, top,
                left / width, top / height,
            )
            self._on_location_result(
                f"RECT {text.strip()} bounds", name, right, bottom,
                right / width, bottom / height,
            )

    @staticmethod
    def normalize_text(text: str) -> str:
        """Convert visible text to a lowercase, accent-free snake_case identifier."""
        text = unicodedata.normalize("NFD", text.strip().lower())
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        text = text.replace("đ", "d")
        return re.sub(r"[^a-z0-9]+", "_", text).strip("_")

    def _update_normalized_text(self, text: str) -> None:
        self.normalized_text.setText(self.normalize_text(text))

    @staticmethod
    def _split_ocr_words(data: dict, target_count: int) -> list[dict]:
        """Group OCR words and retain each group's bounding rectangle."""
        words = []
        count = len(data.get("text", []))
        for i in range(count):
            text = str(data["text"][i]).strip()
            try:
                confidence = float(data["conf"][i])
            except (ValueError, TypeError, KeyError):
                confidence = -1
            if not text or confidence < 0:
                continue
            try:
                x = int(data["left"][i])
                y = int(data["top"][i])
                width = int(data["width"][i])
                height = int(data["height"][i])
                line_key = (
                    int(data["block_num"][i]),
                    int(data["par_num"][i]),
                    int(data["line_num"][i]),
                )
            except (ValueError, TypeError, KeyError):
                continue
            words.append({
                "text": text, "left": x, "top": y, "right": x + width,
                "bottom": y + height, "line": line_key,
            })
        if not words:
            return []

        def combine(group: list[dict]) -> dict:
            return {
                "text": " ".join(word["text"] for word in group).strip(),
                "left": min(word["left"] for word in group),
                "top": min(word["top"] for word in group),
                "right": max(word["right"] for word in group),
                "bottom": max(word["bottom"] for word in group),
            }

        line_keys = sorted(
            {word["line"] for word in words},
            key=lambda key: min(word["top"] for word in words if word["line"] == key),
        )
        if len(line_keys) == 1:
            ordered = sorted(words, key=lambda word: word["left"])
            if target_count <= 1 or len(ordered) < target_count:
                return [combine(ordered)]
            gaps = []
            for i in range(len(ordered) - 1):
                gap = ordered[i + 1]["left"] - ordered[i]["right"]
                gaps.append((gap, i))
            split_positions = sorted(
                index for _gap, index in sorted(gaps, reverse=True)[:target_count - 1]
            )
            groups = []
            start = 0
            for split_at in split_positions:
                groups.append(ordered[start:split_at + 1])
                start = split_at + 1
            groups.append(ordered[start:])
            return [combine(group) for group in groups if group]

        groups = []
        for key in line_keys:
            line_words = sorted(
                (word for word in words if word["line"] == key),
                key=lambda word: word["left"],
            )
            groups.append(combine(line_words))
        return groups

    def recognize_text(self) -> None:
        if self._image_path is None or self._pixmap.isNull():
            QMessageBox.warning(self, "Chưa có ảnh", "Hãy chụp màn hình trước.")
            return
        try:
            with Image.open(self._image_path) as screenshot:
                full_image = screenshot.convert("RGB")
                left, top = 0, 0
                crop = full_image
            try:
                ocr_data = pytesseract.image_to_data(
                    crop, lang="vie+eng", config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                )
            except pytesseract.TesseractError:
                ocr_data = pytesseract.image_to_data(
                    crop, lang="eng", config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                )

            grouped = self._split_ocr_words(ocr_data, self.ocr_item_count.value())
            items = [item["text"] for item in grouped]
            normalized_items = [self.normalize_text(item) for item in items]
            self._ocr_elements = []
            for text, name, item in zip(items, normalized_items, grouped):
                x1 = left + item["left"]
                y1 = top + item["top"]
                x2 = left + item["right"]
                y2 = top + item["bottom"]
                center_x = round((x1 + x2) / 2)
                center_y = round((y1 + y2) / 2)
                self._ocr_elements.append({
                    "name": name,
                    "text": text,
                    "bounds": {"left": x1, "top": y1, "right": x2, "bottom": y2},
                    "corners": [
                        {"name": "top_left", "x_px": x1, "y_px": y1},
                        {"name": "top_right", "x_px": x2, "y_px": y1},
                        {"name": "bottom_right", "x_px": x2, "y_px": y2},
                        {"name": "bottom_left", "x_px": x1, "y_px": y2},
                    ],
                    "center": {"x_px": center_x, "y_px": center_y},
                    "center_ratio": {
                        "x": round(center_x / self._pixmap.width(), 6),
                        "y": round(center_y / self._pixmap.height(), 6),
                    },
                    "bounds_ratio": {
                        "left": round(x1 / self._pixmap.width(), 6),
                        "top": round(y1 / self._pixmap.height(), 6),
                        "right": round(x2 / self._pixmap.width(), 6),
                        "bottom": round(y2 / self._pixmap.height(), 6),
                    },
                })

            self.ocr_text.setText(" | ".join(items))
            self.ocr_items.setPlainText("\n".join(items))
            self.normalized_items.setPlainText("\n".join(normalized_items))
            location_lines = []
            for item in self._ocr_elements:
                b = item["bounds"]
                c = item["center"]
                location_lines.append(
                    f'{item["name"]}: TL=({b["left"]},{b["top"]}) '
                    f'TR=({b["right"]},{b["top"]}) '
                    f'BR=({b["right"]},{b["bottom"]}) '
                    f'BL=({b["left"]},{b["bottom"]}) '
                    f'CENTER=({c["x_px"]},{c["y_px"]})'
                )
            self.ocr_locations.setPlainText("\n".join(location_lines))

            if self._on_ocr_result is not None:
                self._on_ocr_result(items, normalized_items, self._ocr_elements)
            if len(items) == 1 and self.ocr_item_count.value() > 1:
                self.instruction.setText(
                    "OCR chỉ tìm được một cụm chữ. Hãy mở rộng vùng chọn hoặc sửa thủ công "
                    "từng dòng nếu các mục nằm sát nhau."
                )
            else:
                self.instruction.setText(
                    f"Đã tách {len(items)} text trên toàn ảnh. Mỗi text có bounding RECT, 4 góc và trung điểm; "
                    "kiểm tra lại nếu OCR chia cụm chưa đúng."
                )
            if normalized_items and normalized_items[0]:
                self.normalized_text.setText(normalized_items[0])
            if not items:
                QMessageBox.information(
                    self, "Không nhận diện được chữ",
                    "Hãy chọn sát vùng chữ hơn, chụp ảnh rõ hơn hoặc kiểm tra Tesseract OCR.",
                )
        except pytesseract.TesseractNotFoundError:
            QMessageBox.critical(
                self,
                "Chưa cài Tesseract OCR",
                "Ứng dụng đã có thư viện pytesseract nhưng chưa tìm thấy chương trình Tesseract. "
                "Hãy cài Tesseract OCR và dữ liệu ngôn ngữ Vietnamese (vie) + English (eng), "
                "rồi mở lại ứng dụng.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "OCR thất bại", str(exc))


    def undo_point(self) -> None:
        if self._points:
            self._points.pop()
            self.image_view.set_points(self._points)
            self.instruction.setText(f"Còn {len(self._points)} điểm đã chọn.")

    def clear_points(self) -> None:
        self._points.clear()
        self.image_view.set_points(self._points)
        self.instruction.setText("Đã xóa lựa chọn. Chọn chế độ Từng điểm hoặc RECT rồi thao tác trên ảnh.")

    def save_coordinates(self) -> None:
        if self._pixmap.isNull() or self._image_path is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Hãy chụp màn hình trước.")
            return
        if not self._points and not self._ocr_elements:
            QMessageBox.warning(self, "Chưa có tọa độ", "Hãy nhấp chọn điểm hoặc chạy OCR trước.")
            return

        width, height = self._pixmap.width(), self._pixmap.height()
        screen = self.screen_name.text().strip()
        if not screen:
            QMessageBox.warning(self, "Thiếu tên màn hình", "Tên màn hình không được để trống.")
            return
        try:
            if self._points:
                data = self._read_json(
                    LOCATIONS_PATH, {"reference_resolution": [width, height], "screens": {}}
                )
                data.setdefault("reference_resolution", [width, height])
                data.setdefault("screens", {})
                if not isinstance(data["screens"], dict):
                    raise ValueError("Khóa 'screens' trong locations.json không hợp lệ.")
                screen_data = data["screens"].setdefault(screen, {})
                if not isinstance(screen_data, dict):
                    raise ValueError(f"Màn hình {screen!r} trong locations.json không hợp lệ.")
                for x, y, label in self._points:
                    screen_data[label] = {
                        "x": round(x / width, 6), "y": round(y / height, 6),
                        "x_px": x, "y_px": y,
                    }
                LOCATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                LOCATIONS_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

            if self._ocr_elements:
                region = {
                    "name": screen, "serial": self.serial or "desktop",
                    "recognized_text": self.ocr_text.text().strip(),
                    "normalized_text": self.normalized_text.text().strip(),
                    "recognized_items": [
                        item.strip() for item in self.ocr_items.toPlainText().splitlines()
                        if item.strip()
                    ],
                    "normalized_items": [
                        item.strip() for item in self.normalized_items.toPlainText().splitlines()
                        if item.strip()
                    ],
                    "elements": self._ocr_elements,
                    "screenshot": str(self._image_path),
                    "image_resolution": [width, height],
                    "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
                data = self._read_json(REGIONS_PATH, {"regions": {}})
                data.setdefault("regions", {})
                if not isinstance(data["regions"], dict):
                    raise ValueError("Khóa 'regions' trong regions.json không hợp lệ.")
                data["regions"][screen] = region
                REGIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                REGIONS_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

            parts = []
            if self._points:
                parts.append(f"{len(self._points)} tọa độ vào {LOCATIONS_PATH}")
            if self._ocr_elements:
                parts.append(f"{len(self._ocr_elements)} text OCR vào {REGIONS_PATH}")
            message = "Đã lưu " + " và ".join(parts)
            QMessageBox.information(self, "Đã lưu tọa độ", message)
            self.instruction.setText(message)
            if self._on_location_result is not None:
                self._on_location_result("LƯU", screen, 0, 0, 0.0, 0.0, message)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            QMessageBox.critical(self, "Không lưu được tọa độ", str(exc))

    @staticmethod
    def _read_json(path: Path, default: dict) -> dict:
        if not path.exists():
            return default
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"File JSON không phải object: {path}")
        return data
