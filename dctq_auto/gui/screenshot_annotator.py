"""Dialog chụp màn hình ADB và đánh dấu tọa độ trên ảnh gốc."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract

from PySide6.QtCore import QPoint, Qt, QSettings
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QButtonGroup,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
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
        is_cursor_mode=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self._on_image_click = on_image_click
        self._is_region_mode = is_region_mode
        self._on_image_rect = on_image_rect
        self._is_cursor_mode = is_cursor_mode or (lambda: False)
        self._points: list[tuple[int, int, str]] = []
        self._ocr_boxes: list[dict] = []
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._ctrl_gesture = False
        self._pan_start: QPoint | None = None
        self._pan_scroll_start: tuple[int, int] | None = None
        self._scroll_area: QScrollArea | None = None
        self._space_pressed = False
        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_scroll_area(self, scroll_area: QScrollArea) -> None:
        self._scroll_area = scroll_area

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = True
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = False
            event.accept()
            return
        super().keyReleaseEvent(event)

    def set_points(self, points: list[tuple[int, int, str]]) -> None:
        self._points = list(points)
        self.update()

    def set_ocr_boxes(self, boxes: list[dict]) -> None:
        self._ocr_boxes = list(boxes)
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
        if not self._pixmap.isNull():
            scale_x = target.width() / self._pixmap.width()
            scale_y = target.height() / self._pixmap.height()
            if self._ocr_boxes:
                from PySide6.QtCore import QRect
                for index, item in enumerate(self._ocr_boxes, start=1):
                    bounds = (
                        item.get("highlight_bounds", item.get("bounds", {}))
                        if item.get("matched") else item.get("bounds", {})
                    )
                    x1 = target.x() + round(bounds.get("left", 0) * scale_x)
                    y1 = target.y() + round(bounds.get("top", 0) * scale_y)
                    x2 = target.x() + round(bounds.get("right", 0) * scale_x)
                    y2 = target.y() + round(bounds.get("bottom", 0) * scale_y)
                    pen = QPen(Qt.GlobalColor.red if item.get("matched") else Qt.GlobalColor.cyan)
                    pen.setWidth(3 if item.get("matched") else 1)
                    painter.setPen(pen)
                    painter.drawRect(QRect(QPoint(x1, y1), QPoint(x2, y2)).normalized())
                    if item.get("matched"):
                        painter.drawText(x1, max(target.top() + 12, y1 - 4), "MATCH")

            if self._points:
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
        point = event.position().toPoint()
        is_left = event.button() == Qt.MouseButton.LeftButton
        ctrl_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        # Ctrl+drag is a temporary gesture and takes priority over cursor/pan mode.
        if is_left and ctrl_pressed and not self._pixmap.isNull():
            if not self._target_rect().contains(point):
                return
            self._ctrl_gesture = True
            self._drag_start = point
            self._drag_current = point
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
            event.accept()
            return

        pan_requested = (
            event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton)
            or (is_left and (self._space_pressed or self._is_cursor_mode()))
        )
        if pan_requested and self._scroll_area is not None:
            self._pan_start = point
            self._pan_scroll_start = (
                self._scroll_area.horizontalScrollBar().value(),
                self._scroll_area.verticalScrollBar().value(),
            )
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if not is_left or self._pixmap.isNull():
            return
        target = self._target_rect()
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
        point = event.position().toPoint()
        if self._pan_start is not None and self._pan_scroll_start is not None:
            delta = point - self._pan_start
            self._scroll_area.horizontalScrollBar().setValue(
                self._pan_scroll_start[0] - delta.x()
            )
            self._scroll_area.verticalScrollBar().setValue(
                self._pan_scroll_start[1] - delta.y()
            )
            return
        if self._drag_start is not None:
            target = self._target_rect()
            x = min(max(point.x(), target.left()), target.right())
            y = min(max(point.y(), target.top()), target.bottom())
            self._drag_current = QPoint(x, y)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._pan_start is not None and event.button() in (
            Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton
        ):
            self._pan_start = None
            self._pan_scroll_start = None
            self.unsetCursor()
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            return
        start = self._drag_start
        end = self._drag_current or event.position().toPoint()
        was_ctrl_gesture = self._ctrl_gesture
        self._drag_start = None
        self._drag_current = None
        self._ctrl_gesture = False
        self.unsetCursor()
        self.update()
        x1, y1 = self._to_image_point(start)
        x2, y2 = self._to_image_point(end)
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        if was_ctrl_gesture:
            if right - left < 3 and bottom - top < 3:
                self._on_image_click(x1, y1)
            else:
                self._on_image_rect(left, top, right, bottom)
            return
        if right - left < 2 or bottom - top < 2:
            return
        self._on_image_rect(left, top, right, bottom)


class ScreenshotAnnotator(QDialog):
    """Capture an ADB screenshot and save point/region coordinates from that image."""

    def __init__(
        self, serial: str | None, parent=None, on_ocr_result=None, on_location_result=None,
        initial_image: Path | None = None,
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
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.resize(1050, 760)
        self._image_path: Path | None = None
        self._pixmap = QPixmap()
        self._points: list[tuple[int, int, str]] = []
        self._on_location_result = on_location_result
        self._ui_settings = QSettings("DCTQAuto", "DCTQAuto")

        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.image_info = QLabel("Chưa có ảnh.")
        self.image_info.setWordWrap(True)
        self.image_info.setMinimumWidth(80)
        toolbar.addWidget(self.image_info, 1)

        self.capture_button = QPushButton("📂")
        self.capture_button.setFixedSize(34, 30)
        self.capture_button.setToolTip("Chọn file ảnh")
        self.capture_button.clicked.connect(self.choose_screenshot_file)
        toolbar.addWidget(self.capture_button)

        self.camera_button = QPushButton("📷")
        self.camera_button.setFixedSize(34, 30)
        self.camera_button.setToolTip("Chụp màn hình mới từ LDPlayer hoặc desktop")
        self.camera_button.clicked.connect(self.capture_screenshot)
        toolbar.addWidget(self.camera_button)

        self.coordinate_input_button = QPushButton("⌖")
        self.coordinate_input_button.setFixedSize(34, 30)
        self.coordinate_input_button.setToolTip("Nhập X, Y, Width, Height theo pixel ảnh gốc")
        self.coordinate_input_button.clicked.connect(self.input_coordinates)
        toolbar.addWidget(self.coordinate_input_button)

        saved_mode = self._ui_settings.value("screenshot_annotator/mode", "Từng điểm")
        if saved_mode not in ("Từng điểm", "Từng vùng", "Con trỏ"):
            saved_mode = "Từng điểm"
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.point_mode_button = QPushButton("↖")
        self.region_mode_button = QPushButton("▧")
        self.cursor_mode_button = QPushButton("✥")
        for button, tooltip in (
            (self.point_mode_button, "Từng điểm: nhấp ảnh để thêm tọa độ"),
            (self.region_mode_button, "Từng vùng: kéo chọn vùng RECT để phân tích OCR"),
            (self.cursor_mode_button, "Con trỏ: kéo ảnh để di chuyển vùng nhìn"),
        ):
            button.setFixedSize(34, 30)
            button.setCheckable(True)
            button.setToolTip(tooltip)
            self.mode_group.addButton(button)
            toolbar.addWidget(button)
        if saved_mode == "Từng vùng":
            self.region_mode_button.setChecked(True)
        elif saved_mode == "Con trỏ":
            self.cursor_mode_button.setChecked(True)
        else:
            self.point_mode_button.setChecked(True)
        self.point_mode_button.clicked.connect(lambda: self._on_mode_changed("Từng điểm"))
        self.region_mode_button.clicked.connect(lambda: self._on_mode_changed("Từng vùng"))
        self.cursor_mode_button.clicked.connect(lambda: self._on_mode_changed("Con trỏ"))
        root.addLayout(toolbar)

        self._ocr_elements: list[dict] = []
        self._ocr_region: tuple[int, int, int, int] | None = None
        self.instruction = QLabel("Chọn ảnh trong artifacts/screenshots để bắt đầu.")
        self.instruction.setWordWrap(True)
        self.instruction.setVisible(False)

        self._zoom_percent = 100
        self.image_view = ClickableImage(
            QPixmap(),
            self._on_image_click,
            lambda: self._current_mode() == "Từng vùng",
            self._on_image_rect_selected,
            lambda: self._current_mode() == "Con trỏ",
        )
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_view)
        self.image_view.set_scroll_area(self.scroll_area)
        root.addWidget(self.scroll_area, 1)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(100, 300)
        self.zoom_slider.setSingleStep(10)
        self.zoom_slider.setPageStep(25)
        self.zoom_slider.setValue(self._zoom_percent)
        self.zoom_slider.setToolTip("Phóng to ảnh từ 100% đến 300%")
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_row.addWidget(self.zoom_slider, 1)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        zoom_row.addWidget(self.zoom_label)
        root.addLayout(zoom_row)

        bottom = QHBoxLayout()
        self.undo_button = QPushButton("Bỏ điểm cuối")
        self.undo_button.clicked.connect(self.undo_point)
        bottom.addWidget(self.undo_button)
        self.ocr_button = QPushButton("🔎 Phân tích (OCR)")
        self.ocr_button.setToolTip("Chỉ khả dụng ở chế độ Từng vùng")
        self.ocr_button.clicked.connect(self.recognize_text)
        bottom.addWidget(self.ocr_button)
        self._on_mode_changed(self._current_mode())
        self.clear_button = QPushButton("Xóa điểm")
        self.clear_button.clicked.connect(self.clear_points)
        bottom.addWidget(self.clear_button)
        self.save_button = QPushButton("Lưu tọa độ")
        self.save_button.clicked.connect(self.save_coordinates)
        bottom.addWidget(self.save_button)
        root.addLayout(bottom)

        if initial_image is not None and initial_image.is_file():
            self._load_screenshot(initial_image)

    def _on_zoom_changed(self, value: int) -> None:
        self._zoom_percent = value
        self.zoom_label.setText(f"{value}%")
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        """Size the image widget at the selected scale; the scroll area handles panning."""
        if self._pixmap.isNull():
            self.image_view.setMinimumSize(480, 270)
            self.image_view.resize(480, 270)
            return
        width = max(1, round(self._pixmap.width() * self._zoom_percent / 100))
        height = max(1, round(self._pixmap.height() * self._zoom_percent / 100))
        self.image_view.setMinimumSize(1, 1)
        self.image_view.resize(width, height)
        self.image_view.update()

    def _current_mode(self) -> str:
        if self.region_mode_button.isChecked():
            return "Từng vùng"
        if self.cursor_mode_button.isChecked():
            return "Con trỏ"
        return "Từng điểm"

    def _on_mode_changed(self, mode: str) -> None:
        """Persist one of the three exclusive interaction modes."""
        self._ui_settings.setValue("screenshot_annotator/mode", mode)
        is_region_mode = mode == "Từng vùng"
        self.ocr_button.setEnabled(is_region_mode)
        self.ocr_button.setToolTip(
            "Phân tích OCR trong vùng đã chọn" if is_region_mode
            else "OCR chỉ khả dụng ở chế độ Từng vùng."
        )
        if mode == "Từng vùng":
            message = "Từng vùng: kéo chọn một vùng RECT rồi phân tích OCR."
            self.image_view.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "Con trỏ":
            message = "Con trỏ: giữ chuột trái và kéo ảnh để di chuyển vùng nhìn."
            self.image_view.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            message = "Từng điểm: nhấp ảnh để thêm nhiều điểm tọa độ."
            self.image_view.setCursor(Qt.CursorShape.ArrowCursor)
        self.instruction.setText(message)
        self.image_view.update()

    def choose_screenshot_file(self) -> None:
        """Allow selecting only an image directly inside artifacts/screenshots."""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh màn hình",
            str(SCREENSHOT_DIR.resolve()),
            "Ảnh màn hình (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not filename:
            return
        selected = Path(filename).resolve()
        allowed_dir = SCREENSHOT_DIR.resolve()
        if selected.parent != allowed_dir or selected.suffix.lower() not in {
            ".png", ".jpg", ".jpeg", ".bmp", ".webp"
        }:
            QMessageBox.warning(
                self,
                "File không hợp lệ",
                "Chỉ được chọn file ảnh nằm trực tiếp trong artifacts/screenshots.",
            )
            return
        self._load_screenshot(selected)

    def _load_screenshot(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Không mở được ảnh", f"Không đọc được file ảnh: {path}")
            return
        self._image_path = path
        self._pixmap = pixmap
        self._points.clear()
        self._ocr_elements = []
        self._ocr_region = None
        self.image_view._pixmap = self._pixmap
        self._apply_zoom()
        self.image_view.set_points(self._points)
        self.image_view.set_ocr_boxes([])
        self.image_info.setText(
            f"{self._image_path} — ảnh gốc {self._pixmap.width()}×{self._pixmap.height()} px"
        )
        self.instruction.setText(
            "Đã mở ảnh. Chọn Từng điểm để lưu nhiều tọa độ hoặc Từng vùng để phân tích OCR một vùng."
        )
        self.image_view.update()

    def input_coordinates(self) -> None:
        """Open a validated X/Y/Width/Height editor in original-image pixels."""
        if self._pixmap.isNull():
            QMessageBox.information(self, "Chưa có ảnh", "Hãy mở ảnh chụp màn hình trước.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Nhập vị trí")
        form = QFormLayout(dialog)
        x_input = QLineEdit()
        y_input = QLineEdit()
        width_input = QLineEdit()
        height_input = QLineEdit()
        for widget, placeholder in (
            (x_input, "Bắt buộc, từ 0 đến chiều rộng ảnh - 1"),
            (y_input, "Bắt buộc, từ 0 đến chiều cao ảnh - 1"),
            (width_input, "Để trống nếu nhập một điểm"),
            (height_input, "Để trống nếu nhập một điểm"),
        ):
            widget.setPlaceholderText(placeholder)
        form.addRow("X:", x_input)
        form.addRow("Y:", y_input)
        form.addRow("Width:", width_input)
        form.addRow("Height:", height_input)
        hint = QLabel(
            f"Ảnh gốc: {self._pixmap.width()} × {self._pixmap.height()} px. "
            "Width và Height phải cùng để trống hoặc cùng là số lớn hơn 0."
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        form.addRow(buttons)

        fields = {
            "x": x_input, "y": y_input,
            "width": width_input, "height": height_input,
        }

        def mark_invalid(names: set[str]) -> None:
            for name, widget in fields.items():
                widget.setStyleSheet(
                    "QLineEdit { border: 1px solid #dc2626; background: #fff1f2; }"
                    if name in names else ""
                )

        def accept_coordinates() -> None:
            invalid: set[str] = set()
            values: dict[str, int | None] = {}
            for name in ("x", "y", "width", "height"):
                raw = fields[name].text().strip()
                if not raw:
                    values[name] = None
                    continue
                try:
                    values[name] = int(raw)
                except ValueError:
                    values[name] = None
                    invalid.add(name)

            if values["x"] is None:
                invalid.add("x")
            if values["y"] is None:
                invalid.add("y")
            image_width, image_height = self._pixmap.width(), self._pixmap.height()
            if values["x"] is not None and not (0 <= values["x"] < image_width):
                invalid.add("x")
            if values["y"] is not None and not (0 <= values["y"] < image_height):
                invalid.add("y")

            width_empty = not width_input.text().strip()
            height_empty = not height_input.text().strip()
            is_point = width_empty and height_empty
            if width_empty != height_empty:
                invalid.update(("width", "height"))
            elif not is_point:
                for name in ("width", "height"):
                    if values[name] is None or values[name] <= 0:
                        invalid.add(name)
                if not invalid and values["x"] is not None and values["y"] is not None:
                    if values["x"] + values["width"] > image_width:
                        invalid.add("width")
                    if values["y"] + values["height"] > image_height:
                        invalid.add("height")

            mark_invalid(invalid)
            if invalid:
                hint.setText(
                    "Giá trị chưa hợp lệ: X/Y phải nằm trong ảnh; Width/Height phải cùng để trống "
                    "hoặc là số nguyên > 0 và vùng RECT phải nằm trọn trong ảnh."
                )
                return

            x, y = values["x"], values["y"]
            self._ocr_elements = []
            self.image_view.set_ocr_boxes([])
            if is_point:
                self.point_mode_button.setChecked(True)
                self._on_mode_changed("Từng điểm")
                self._ocr_region = None
                self._points = [(x, y, "manual_point")]
                self.image_view.set_points(self._points)
                self.instruction.setText(f"Đã nhập point: ({x}, {y}) trên ảnh gốc.")
                if self._on_location_result is not None:
                    self._on_location_result(
                        "Point nhập tay", "manual_point", x, y,
                        x / image_width, y / image_height,
                    )
            else:
                width, height = values["width"], values["height"]
                right, bottom = x + width, y + height
                self.region_mode_button.setChecked(True)
                self._on_mode_changed("Từng vùng")
                self._ocr_region = (x, y, right, bottom)
                self._points = [
                    (x, y, "manual_rect_top_left"),
                    (right, y, "manual_rect_top_right"),
                    (right, bottom, "manual_rect_bottom_right"),
                    (x, bottom, "manual_rect_bottom_left"),
                ]
                self.image_view.set_points(self._points)
                self.instruction.setText(
                    f"Đã nhập RECT: x={x}, y={y}, w={width}, h={height}. "
                    "Nhấn Phân tích (OCR) để nhận diện chữ trong vùng này."
                )
                if self._on_location_result is not None:
                    self._on_location_result(
                        "RECT nhập tay", "manual_rect", x, y,
                        x / image_width, y / image_height,
                    )
            dialog.accept()

        buttons.accepted.connect(accept_coordinates)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def capture_screenshot(self) -> None:
        """Capture a screenshot when invoked programmatically."""
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            if self.capture_desktop:
                screen = QGuiApplication.primaryScreen()
                if screen is None:
                    raise RuntimeError("Không tìm thấy màn hình desktop.")
                path = SCREENSHOT_DIR / f"desktop_{timestamp}.png"
                if not screen.grabWindow(0).save(str(path), "PNG"):
                    raise RuntimeError("Không lưu được ảnh chụp desktop.")
            else:
                device = AdbClient(self.serial).connect()
                safe_serial = self.serial.replace(":", "_").replace("/", "_").replace("\\", "_")
                path = SCREENSHOT_DIR / f"{safe_serial}_{timestamp}.png"
                device.screenshot().save(str(path))
            self._load_screenshot(path)
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
        # Remember the selected rectangle as the OCR input region.
        self._ocr_region = (left, top, right, bottom)
        self._ocr_elements = []
        self.image_view.set_ocr_boxes([])
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
    def _split_ocr_words(data: dict, min_confidence: float = 45.0) -> list[dict]:
        """Group reliable OCR words by their actual Tesseract text line."""
        words = []
        count = len(data.get("text", []))
        for i in range(count):
            text = re.sub(r"\s+", " ", str(data["text"][i])).strip()
            try:
                confidence = float(data["conf"][i])
                x = int(data["left"][i])
                y = int(data["top"][i])
                width = int(data["width"][i])
                height = int(data["height"][i])
                line_key = (
                    int(data["block_num"][i]),
                    int(data["par_num"][i]),
                    int(data["line_num"][i]),
                )
            except (ValueError, TypeError, KeyError, IndexError):
                continue

            # Discard low-confidence, tiny, punctuation-only and obvious one-character noise.
            alphanumeric = re.sub(r"[^\w]", "", text, flags=re.UNICODE)
            if (
                not text or confidence < min_confidence or width < 4 or height < 7
                or len(alphanumeric) < 2
            ):
                continue
            words.append({
                "text": text, "left": x, "top": y, "right": x + width,
                "bottom": y + height, "line": line_key, "confidence": confidence,
            })
        if not words:
            return []

        groups: dict[tuple[int, int, int], list[dict]] = {}
        for word in words:
            groups.setdefault(word["line"], []).append(word)

        result = []
        for key in sorted(
            groups,
            key=lambda k: (
                min(word["top"] for word in groups[k]),
                min(word["left"] for word in groups[k]),
            ),
        ):
            group = sorted(groups[key], key=lambda word: word["left"])
            text = " ".join(word["text"] for word in group).strip()
            # Reject output that is mostly symbols or OCR artifacts.
            useful_chars = len(re.findall(r"[\w]", text, flags=re.UNICODE))
            if useful_chars < 2:
                continue
            result.append({
                "text": text,
                "left": min(word["left"] for word in group),
                "top": min(word["top"] for word in group),
                "right": max(word["right"] for word in group),
                "bottom": max(word["bottom"] for word in group),
                "confidence": round(sum(word["confidence"] for word in group) / len(group), 1),
                "words": [
                    {
                        "text": word["text"],
                        "left": word["left"],
                        "top": word["top"],
                        "right": word["right"],
                        "bottom": word["bottom"],
                    }
                    for word in group
                ],
            })
        return result

    def recognize_text(self) -> None:
        if self._image_path is None or self._pixmap.isNull():
            QMessageBox.warning(self, "Chưa có ảnh", "Hãy chọn ảnh trong artifacts/screenshots trước.")
            return

        rect_mode = self._current_mode() == "Từng vùng"
        if not rect_mode:
            return
        if self._ocr_region is None:
            QMessageBox.information(
                self, "Chưa chọn RECT",
                "Hãy kéo chọn một vùng RECT trên ảnh trước khi chạy OCR. OCR sẽ chỉ phân tích vùng đó và trả về hộp tọa độ cho từng dòng chữ nhận diện được.",
            )
            return

        target_text, accepted = QInputDialog.getText(
            self,
            "Text cần phát hiện (không bắt buộc)",
            "Nhập text muốn tìm, ví dụ quan_doan. Để trống để hiển thị toàn bộ kết quả OCR:",
            text="",
        )
        if not accepted:
            return
        target_normalized = self.normalize_text(target_text) if target_text.strip() else ""

        try:
            # OCR input is the selected region in Từng vùng mode; point mode cannot run OCR.
            with Image.open(self._image_path) as screenshot:
                original_size = screenshot.size
                if rect_mode:
                    left, top, right, bottom = self._ocr_region
                    left = max(0, min(original_size[0], left))
                    top = max(0, min(original_size[1], top))
                    right = max(left + 1, min(original_size[0], right))
                    bottom = max(top + 1, min(original_size[1], bottom))
                    source_region = screenshot.convert("RGB").crop((left, top, right, bottom))
                    offset_x, offset_y = left, top
                else:
                    source_region = screenshot.convert("RGB")
                    offset_x, offset_y = 0, 0

                image = ImageOps.autocontrast(source_region.convert("L"))
                scale = 2
                image = image.resize(
                    (image.width * scale, image.height * scale),
                    Image.Resampling.LANCZOS,
                )

            try:
                ocr_data = pytesseract.image_to_data(
                    image, lang="vie+eng", config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                )
            except pytesseract.TesseractError:
                ocr_data = pytesseract.image_to_data(
                    image, lang="eng", config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                )

            grouped = self._split_ocr_words(ocr_data, min_confidence=45.0)
            self._ocr_elements = []
            self.image_view.set_ocr_boxes([])
            image_width, image_height = original_size

            if rect_mode:
                # Return each OCR text line with its own bounding box in original-image coordinates.
                for item in grouped:
                    x1 = max(left, min(right, left + round(item["left"] / scale)))
                    y1 = max(top, min(bottom, top + round(item["top"] / scale)))
                    x2 = max(x1, min(right, left + round(item["right"] / scale)))
                    y2 = max(y1, min(bottom, top + round(item["bottom"] / scale)))
                    width, height = x2 - x1, y2 - y1
                    if width < 3 or height < 3:
                        continue
                    center_x = round((x1 + x2) / 2)
                    center_y = round((y1 + y2) / 2)
                    word_bounds = []
                    for word in item.get("words", []):
                        wx1 = max(left, min(right, left + round(word["left"] / scale)))
                        wy1 = max(top, min(bottom, top + round(word["top"] / scale)))
                        wx2 = max(wx1, min(right, left + round(word["right"] / scale)))
                        wy2 = max(wy1, min(bottom, top + round(word["bottom"] / scale)))
                        if wx2 - wx1 >= 2 and wy2 - wy1 >= 2:
                            word_bounds.append({
                                "text": word["text"],
                                "bounds": {
                                    "left": wx1, "top": wy1, "right": wx2, "bottom": wy2
                                },
                            })
                    self._ocr_elements.append({
                        "name": self.normalize_text(item["text"]),
                        "text": item["text"],
                        "confidence": item["confidence"],
                        "word_bounds": word_bounds,
                        "bounds": {"left": x1, "top": y1, "right": x2, "bottom": y2},
                        "rect": {"x": x1, "y": y1, "width": width, "height": height},
                        "corners": [
                            {"name": "top_left", "x_px": x1, "y_px": y1},
                            {"name": "top_right", "x_px": x2, "y_px": y1},
                            {"name": "bottom_right", "x_px": x2, "y_px": y2},
                            {"name": "bottom_left", "x_px": x1, "y_px": y2},
                        ],
                        "center": {"x_px": center_x, "y_px": center_y},
                        "center_ratio": {
                            "x": round(center_x / image_width, 6),
                            "y": round(center_y / image_height, 6),
                        },
                        "bounds_ratio": {
                            "left": round(x1 / image_width, 6),
                            "top": round(y1 / image_height, 6),
                            "right": round(x2 / image_width, 6),
                            "bottom": round(y2 / image_height, 6),
                        },
                    })
                self.image_view.set_ocr_boxes(self._ocr_elements)
            else:
                # Point mode retains whole-image OCR, but only accepts filtered text lines.
                for item in grouped:
                    x1 = max(0, min(image_width, offset_x + round(item["left"] / scale)))
                    y1 = max(0, min(image_height, offset_y + round(item["top"] / scale)))
                    x2 = max(x1, min(image_width, offset_x + round(item["right"] / scale)))
                    y2 = max(y1, min(image_height, offset_y + round(item["bottom"] / scale)))
                    width, height = x2 - x1, y2 - y1
                    if width < 3 or height < 3:
                        continue
                    center_x = round((x1 + x2) / 2)
                    center_y = round((y1 + y2) / 2)
                    self._ocr_elements.append({
                        "name": self.normalize_text(item["text"]),
                        "text": item["text"],
                        "confidence": item["confidence"],
                        "bounds": {"left": x1, "top": y1, "right": x2, "bottom": y2},
                        "rect": {"x": x1, "y": y1, "width": width, "height": height},
                        "corners": [
                            {"name": "top_left", "x_px": x1, "y_px": y1},
                            {"name": "top_right", "x_px": x2, "y_px": y1},
                            {"name": "bottom_right", "x_px": x2, "y_px": y2},
                            {"name": "bottom_left", "x_px": x1, "y_px": y2},
                        ],
                        "center": {"x_px": center_x, "y_px": center_y},
                        "center_ratio": {
                            "x": round(center_x / image_width, 6),
                            "y": round(center_y / image_height, 6),
                        },
                        "bounds_ratio": {
                            "left": round(x1 / image_width, 6),
                            "top": round(y1 / image_height, 6),
                            "right": round(x2 / image_width, 6),
                            "bottom": round(y2 / image_height, 6),
                        },
                    })

            if target_normalized:
                for item in self._ocr_elements:
                    item["matched"] = False
                    item.pop("highlight_bounds", None)
                    # Match normalized word sequences so punctuation such as "-" or "." is
                    # treated consistently, then highlight only the matched word(s), not the
                    # entire OCR line.
                    words = item.get("word_bounds", [])
                    for start_index in range(len(words)):
                        matched_sequence = []
                        for end_index in range(start_index, len(words)):
                            matched_sequence.append(words[end_index])
                            sequence_text = "_".join(
                                self.normalize_text(word["text"]) for word in matched_sequence
                            ).strip("_")
                            if target_normalized == sequence_text:
                                item["matched"] = True
                                item["highlight_bounds"] = {
                                    "left": min(word["bounds"]["left"] for word in matched_sequence),
                                    "top": min(word["bounds"]["top"] for word in matched_sequence),
                                    "right": max(word["bounds"]["right"] for word in matched_sequence),
                                    "bottom": max(word["bounds"]["bottom"] for word in matched_sequence),
                                }
                                break
                        if item["matched"]:
                            break
                self.image_view.set_ocr_boxes(self._ocr_elements)
            else:
                for item in self._ocr_elements:
                    item["matched"] = False
                    item.pop("highlight_bounds", None)
                self.image_view.set_ocr_boxes(self._ocr_elements)

            items = [item["text"] for item in self._ocr_elements]
            normalized_items = [item["name"] for item in self._ocr_elements]
            if self._on_ocr_result is not None:
                self._on_ocr_result(items, normalized_items, self._ocr_elements)

            if not items:
                self.instruction.setText("Không tìm thấy text đủ tin cậy trong vùng đã chọn." if rect_mode else "Không tìm thấy cụm chữ đủ tin cậy.")
                QMessageBox.information(
                    self, "Không nhận diện được chữ",
                    "Không tìm thấy text đủ tin cậy trong vùng đã chọn." if rect_mode
                    else "Không tìm thấy text có độ tin cậy đủ cao. Hãy thử ảnh rõ hơn.",
                )
            else:
                if target_normalized:
                    matches = [item for item in self._ocr_elements if item.get("matched")]
                    if matches:
                        self.instruction.setText(
                            f"Tìm thấy '{target_text.strip()}' trong {len(matches)} vùng chữ. "
                            "Vùng khớp được viền đỏ; các vùng OCR khác viền xanh."
                        )
                    else:
                        self.instruction.setText(
                            f"Không tìm thấy '{target_text.strip()}'. Các vùng OCR nhận diện được "
                            "vẫn hiển thị viền xanh để bạn kiểm tra."
                        )
                else:
                    self.instruction.setText(f"Đã nhận diện {len(items)} cụm chữ trong vùng.")
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
        self.instruction.setText("Đã xóa các điểm đã chọn.")

    def save_coordinates(self) -> None:
        if self._pixmap.isNull() or self._image_path is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Hãy chọn ảnh trong artifacts/screenshots trước.")
            return
        if not self._points and not self._ocr_elements:
            QMessageBox.warning(self, "Chưa có tọa độ", "Hãy nhấp chọn điểm hoặc chạy OCR trước.")
            return

        width, height = self._pixmap.width(), self._pixmap.height()
        screen = self._image_path.stem
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
                    "recognized_text": " | ".join(item["text"] for item in self._ocr_elements),
                    "normalized_text": " | ".join(item["name"] for item in self._ocr_elements),
                    "recognized_items": [item["text"] for item in self._ocr_elements],
                    "normalized_items": [item["name"] for item in self._ocr_elements],
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
