"""Dialog chụp màn hình ADB và đánh dấu tọa độ trên ảnh gốc."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np
import cv2
import pytesseract

from PySide6.QtCore import QPoint, Qt, QSettings
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QFileDialog,
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.adb.client import AdbClient


LOCATIONS_PATH = Path("dctq_auto/tasks/common/locations.json")
REGIONS_PATH = Path("dctq_auto/tasks/common/regions.json")
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
        self._selected_region: tuple[int, int, int, int] | None = None
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

    def set_selected_region(self, region: tuple[int, int, int, int] | None) -> None:
        self._selected_region = region
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
                    pen = QPen(Qt.GlobalColor.red if item.get("matched") else Qt.GlobalColor.green)
                    pen.setWidth(3 if item.get("matched") else 2)
                    painter.setPen(pen)
                    painter.drawRect(QRect(QPoint(x1, y1), QPoint(x2, y2)).normalized())

            if self._selected_region is not None:
                from PySide6.QtCore import QRect
                left, top, right, bottom = self._selected_region
                x1 = target.x() + round(left * scale_x)
                y1 = target.y() + round(top * scale_y)
                x2 = target.x() + round(right * scale_x)
                y2 = target.y() + round(bottom * scale_y)
                pen = QPen(Qt.GlobalColor.green)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(QRect(QPoint(x1, y1), QPoint(x2, y2)).normalized())

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
        self._image_path: Path | None = None
        self._pixmap = QPixmap()
        self._points: list[tuple[int, int, str]] = []
        self._on_location_result = on_location_result
        self._ui_settings = QSettings("DCTQAuto", "DCTQAuto")
        self._saved_window_width = int(
            self._ui_settings.value("screenshot_annotator/window_width", 1050)
        )

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

        self.coordinate_input_button = QPushButton("⌨")
        self.coordinate_input_button.setFixedSize(34, 30)
        self.coordinate_input_button.setToolTip("Nhập X, Y, Width, Height theo pixel ảnh gốc")
        self.coordinate_input_button.clicked.connect(self.input_coordinates)
        toolbar.addWidget(self.coordinate_input_button)

        saved_mode = self._ui_settings.value("screenshot_annotator/mode", "Từng điểm")
        if saved_mode not in ("Từng điểm", "Từng vùng", "Con trỏ"):
            saved_mode = "Từng điểm"
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.point_mode_button = QPushButton("⌖")
        self.region_mode_button = QPushButton("▧")
        self.cursor_mode_button = QPushButton("↖")
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

        self._zoom_percent = max(
            25, min(200, int(self._ui_settings.value("screenshot_annotator/zoom_percent", 100)))
        )
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
        self.zoom_slider.setRange(25, 200)
        self.zoom_slider.setSingleStep(10)
        self.zoom_slider.setPageStep(25)
        self.zoom_slider.setValue(self._zoom_percent)
        self.zoom_slider.setToolTip("Thu nhỏ hoặc phóng to ảnh từ 25% đến 200%")
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_row.addWidget(self.zoom_slider, 1)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        zoom_row.addWidget(self.zoom_label)
        root.addLayout(zoom_row)

        bottom = QHBoxLayout()
        self.clear_button = QPushButton("🧹 Làm mới")
        self.clear_button.setToolTip("Xóa toàn bộ điểm, RECT đã chọn và kết quả OCR trên ảnh.")
        self.clear_button.clicked.connect(self.clear_points)
        bottom.addWidget(self.clear_button)
        self.undo_button = QPushButton("↩️ Bỏ điểm cuối")
        self.undo_button.clicked.connect(self.undo_point)
        bottom.addWidget(self.undo_button)
        self.ocr_button = QPushButton("🔍 Phân tích OCR")
        self.ocr_button.setToolTip("Chỉ khả dụng ở chế độ Từng vùng")
        self.ocr_button.clicked.connect(self.recognize_text)
        bottom.addWidget(self.ocr_button)
        self.save_button = QPushButton("💾 Lưu file")
        self.save_button.clicked.connect(self.save_coordinates)
        bottom.addWidget(self.save_button)
        self._on_mode_changed(self._current_mode())
        root.addLayout(bottom)

        if initial_image is not None and initial_image.is_file():
            self._load_screenshot(initial_image)

    def showEvent(self, event) -> None:
        """Dock the annotator to the primary screen's left edge and fill its height."""
        super().showEvent(event)
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        default_width = min(1050, available.width())
        width = self._saved_window_width or default_width

        # First place the client area at the screen origin so Qt has established
        # the native frame geometry. Then account for title-bar/border margins:
        # QWidget.geometry() excludes the native frame, while availableGeometry()
        # describes the usable screen including where that frame must fit.
        self.setGeometry(available.left(), available.top(), width, available.height())
        frame = self.frameGeometry()
        client = self.geometry()
        left_margin = client.left() - frame.left()
        top_margin = client.top() - frame.top()
        frame_width = max(0, frame.width() - client.width())
        frame_height = max(0, frame.height() - client.height())

        width = max(1, min(width, available.width() - frame_width))
        height = max(1, available.height() - frame_height)
        self.setGeometry(
            available.left() + left_margin,
            available.top() + top_margin,
            width,
            height,
        )

    def closeEvent(self, event) -> None:
        """Persist the annotator width; its left position and full height are defaults."""
        self._ui_settings.setValue(
            "screenshot_annotator/window_width", self.width()
        )
        super().closeEvent(event)

    def _on_zoom_changed(self, value: int) -> None:
        self._zoom_percent = value
        self.zoom_label.setText(f"{value}%")
        self._ui_settings.setValue("screenshot_annotator/zoom_percent", value)
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
        can_analyze = is_region_mode or self._ocr_region is not None
        self.ocr_button.setEnabled(can_analyze)
        self.ocr_button.setToolTip(
            "Phân tích OCR trong vùng RECT đã chọn" if can_analyze
            else "Chọn Từng vùng hoặc giữ Ctrl và kéo để chọn RECT trước."
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
        self.image_view.set_selected_region(None)
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
                # RECT được lưu riêng; không tạo các điểm góc manual_*.
                self._points = []
                self.image_view.set_points(self._points)
                self.image_view.set_selected_region(self._ocr_region)
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
        self._points = []
        self.image_view.set_points(self._points)
        self.image_view.set_ocr_boxes([])
        self.image_view.set_selected_region(self._ocr_region)
        self.ocr_button.setEnabled(True)
        self.ocr_button.setToolTip("Phân tích OCR trong vùng RECT đã chọn")
        self.instruction.setText(f"Đã chọn RECT '{name}'. Có thể nhấn Phân tích (OCR).")
        if self._on_location_result is not None:
            width, height = self._pixmap.width(), self._pixmap.height()
            self._on_location_result(
                f"RECT {text.strip()}",
                name,
                left,
                top,
                left / width,
                top / height,
                f"Đã chọn RECT {name}: ({left}, {top}, {right}, {bottom})",
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
        if self._current_mode() != "Từng vùng" and self._ocr_region is None:
            return
        if self._ocr_region is None:
            QMessageBox.information(
                self, "Chưa chọn RECT",
                "Hãy kéo chọn một vùng RECT trên ảnh trước khi chạy OCR.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Thiết lập phân tích OCR")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        steps_group = QGroupBox("Steps")
        steps_layout = QGridLayout(steps_group)
        step_checks = {}
        step_names = [
            ("gray", "gray", True), ("clahe", "clahe", True),
            ("otsu", "otsu", True), ("otsu_inverted", "otsu_inverted", True),
            ("color_text", "color_text", True), ("white_text", "white_text", False),
        ]
        saved_steps = self._ui_settings.value(
            "screenshot_annotator/ocr_steps", [key for key, _label, checked in step_names if checked]
        )
        if isinstance(saved_steps, str):
            saved_steps = [item for item in saved_steps.split(",") if item]
        saved_steps = set(saved_steps)
        for index, (key, label, checked) in enumerate(step_names):
            checkbox = QCheckBox(label)
            checkbox.setChecked(key in saved_steps if self._ui_settings.contains("screenshot_annotator/ocr_steps") else checked)
            step_checks[key] = checkbox
            steps_layout.addWidget(checkbox, index // 3, index % 3)
        layout.addWidget(steps_group)

        psm_group = QGroupBox("PSM")
        psm_layout = QGridLayout(psm_group)
        psm_checks = {}
        saved_psms = self._ui_settings.value("screenshot_annotator/ocr_psms", [6, 7, 11])
        if isinstance(saved_psms, str):
            saved_psms = [item for item in saved_psms.split(",") if item]
        saved_psms = {int(item) for item in saved_psms}
        for index, psm in enumerate(range(14)):
            checkbox = QCheckBox(str(psm))
            checkbox.setChecked(psm in saved_psms)
            psm_checks[psm] = checkbox
            psm_layout.addWidget(checkbox, index // 7, index % 7)
        layout.addWidget(psm_group)

        target_text_input = QLineEdit(str(self._ui_settings.value("screenshot_annotator/ocr_target_text", "")))
        target_text_input.setPlaceholderText("Để trống để hiển thị toàn bộ kết quả OCR")
        text_color_input = QLineEdit(str(self._ui_settings.value("screenshot_annotator/ocr_text_color", "#FFFFFF")))
        background_color_input = QLineEdit(str(self._ui_settings.value("screenshot_annotator/ocr_background_color", "#202020")))
        border_color_input = QLineEdit(str(self._ui_settings.value("screenshot_annotator/ocr_border_color", "")))
        output_background_color_input = QLineEdit(
            str(self._ui_settings.value("screenshot_annotator/ocr_output_background_color", "#FFFFFF"))
        )
        tolerance_input = QDoubleSpinBox()

        def add_color_preview(input_widget: QLineEdit, initial_color: str) -> QWidget:
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            row.addWidget(input_widget, 1)
            preview = QLabel()
            preview.setFixedSize(24, 24)
            preview.setToolTip("Xem trước màu")
            preview.setStyleSheet(
                f"background-color: {initial_color}; border: 1px solid #777; border-radius: 3px;"
            )
            row.addWidget(preview)

            def update_preview(value: str) -> None:
                color = value.strip()
                if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                    preview.setStyleSheet(
                        f"background-color: {color}; border: 1px solid #777; border-radius: 3px;"
                    )
                else:
                    preview.setStyleSheet(
                        "background-color: transparent; border: 1px dashed #dc2626; border-radius: 3px;"
                    )
            input_widget.textChanged.connect(update_preview)
            return container

        text_color_row = add_color_preview(text_color_input, "#FFFFFF")
        background_color_row = add_color_preview(background_color_input, "#202020")
        border_color_row = add_color_preview(border_color_input, "#FFFFFF")
        output_background_color_row = add_color_preview(output_background_color_input, "#FFFFFF")
        tolerance_input.setRange(1, 255)
        tolerance_input.setDecimals(1)
        tolerance_input.setValue(float(self._ui_settings.value("screenshot_annotator/ocr_tolerance", 38.0)))
        tolerance_input.setToolTip("Ngưỡng sai khác màu; dùng cho bước color_text và lọc viền.")
        form.addRow("Text cần phát hiện:", target_text_input)
        form.addRow("Text-color (#RRGGBB hoặc R,G,B):", text_color_row)
        form.addRow("Background-color:", background_color_row)
        form.addRow("Border-color (để trống nếu không có):", border_color_row)
        form.addRow("Output-background-color:", output_background_color_row)
        form.addRow("Màu nền đầu ra của color_text (HEX #RRGGBB hoặc R,G,B).")
        form.addRow("Color-tolerance:", tolerance_input)
        layout.addLayout(form)

        save_files_checkbox = QCheckBox("Lưu file xử lý và kết quả OCR (giống scripts/ocr_debug.py)")
        save_files_checkbox.setChecked(
            self._ui_settings.value("screenshot_annotator/ocr_save_files", False, type=bool)
        )
        layout.addWidget(save_files_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        target_text = target_text_input.text().strip()
        target_normalized = self.normalize_text(target_text) if target_text else ""
        selected_steps = [key for key, checkbox in step_checks.items() if checkbox.isChecked()]
        selected_psms = [psm for psm, checkbox in psm_checks.items() if checkbox.isChecked()]
        if not selected_steps:
            QMessageBox.warning(self, "Thiếu steps", "Hãy chọn ít nhất một step.")
            return
        if not selected_psms:
            QMessageBox.warning(self, "Thiếu PSM", "Hãy chọn ít nhất một PSM.")
            return

        def parse_rgb(value: str, field_name: str, optional: bool = False):
            value = value.strip()
            if not value and optional:
                return None
            try:
                if value.startswith("#"):
                    raw = value[1:]
                    if len(raw) != 6:
                        raise ValueError
                    rgb = tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
                else:
                    rgb = tuple(int(part.strip()) for part in value.split(","))
                if len(rgb) != 3 or any(channel < 0 or channel > 255 for channel in rgb):
                    raise ValueError
                return rgb
            except ValueError:
                raise ValueError(f"{field_name} không hợp lệ: {value}")

        try:
            text_rgb = parse_rgb(text_color_input.text(), "Text-color")
            background_rgb = parse_rgb(background_color_input.text(), "Background-color")
            border_rgb = parse_rgb(border_color_input.text(), "Border-color", optional=True)
            output_background_rgb = parse_rgb(
                output_background_color_input.text(), "Output-background-color"
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Màu không hợp lệ", str(exc))
            return

        # Lưu cấu hình sau khi người dùng xác nhận và các giá trị màu hợp lệ.
        self._ui_settings.setValue("screenshot_annotator/ocr_target_text", target_text_input.text())
        self._ui_settings.setValue("screenshot_annotator/ocr_steps", selected_steps)
        self._ui_settings.setValue("screenshot_annotator/ocr_psms", selected_psms)
        self._ui_settings.setValue("screenshot_annotator/ocr_text_color", text_color_input.text().strip())
        self._ui_settings.setValue("screenshot_annotator/ocr_background_color", background_color_input.text().strip())
        self._ui_settings.setValue("screenshot_annotator/ocr_border_color", border_color_input.text().strip())
        self._ui_settings.setValue(
            "screenshot_annotator/ocr_output_background_color", output_background_color_input.text().strip()
        )
        self._ui_settings.setValue("screenshot_annotator/ocr_tolerance", tolerance_input.value())
        self._ui_settings.setValue("screenshot_annotator/ocr_save_files", save_files_checkbox.isChecked())
        self._ui_settings.sync()

        print(
            "[OCR] Bắt đầu phân tích: "
            f"image={self._image_path}, rect={self._ocr_region}, "
            f"target={target_text!r}, steps={selected_steps}, psm={selected_psms}, "
            f"text_color={text_rgb}, background_color={background_rgb}, "
            f"border_color={border_rgb}, output_background_color={output_background_rgb}, "
            f"tolerance={tolerance_input.value()}, "
            f"save_files={save_files_checkbox.isChecked()}",
            flush=True,
        )
        try:
            with Image.open(self._image_path) as screenshot:
                original_size = screenshot.size
                left, top, right, bottom = self._ocr_region
                left = max(0, min(original_size[0], left))
                top = max(0, min(original_size[1], top))
                right = max(left + 1, min(original_size[0], right))
                bottom = max(top + 1, min(original_size[1], bottom))
                source_region = screenshot.convert("RGB").crop((left, top, right, bottom))
                rgb_image = np.asarray(source_region)
                bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
                scale = 3
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
                gray = cv2.copyMakeBorder(gray, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255)

                variants = {}
                if "gray" in selected_steps:
                    variants["gray"] = gray
                contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
                if "clahe" in selected_steps:
                    variants["clahe"] = contrast
                _, otsu = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                if "otsu" in selected_steps:
                    variants["otsu"] = otsu
                _, otsu_inv = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                if "otsu_inverted" in selected_steps:
                    variants["otsu_inverted"] = otsu_inv

                tolerance = float(tolerance_input.value())
                if "color_text" in selected_steps:
                    def color_distance(rgb, reference):
                        ref_lab = cv2.cvtColor(np.uint8([[list(reference)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
                        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
                        return np.linalg.norm(lab - ref_lab, axis=2)
                    text_distance = color_distance(rgb_image, text_rgb)
                    bg_distance = color_distance(rgb_image, background_rgb)
                    mask = (text_distance <= tolerance) & (text_distance < bg_distance)
                    if border_rgb is not None:
                        mask &= color_distance(rgb_image, border_rgb) > tolerance
                    # Chữ được giữ là đen; các pixel còn lại dùng màu nền đầu ra người dùng chọn.
                    output_background = np.array(output_background_rgb, dtype=np.uint8)
                    color_output = np.empty((*mask.shape, 3), dtype=np.uint8)
                    color_output[:] = output_background
                    color_output[mask] = (0, 0, 0)
                    color_output = cv2.resize(
                        color_output, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST
                    )
                    color_output = cv2.copyMakeBorder(
                        color_output, 18, 18, 18, 18, cv2.BORDER_CONSTANT,
                        value=tuple(int(channel) for channel in output_background_rgb),
                    )
                    variants["color_text"] = color_output
                if "white_text" in selected_steps:
                    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
                    mask = cv2.inRange(hsv, np.array([0, 0, 135], dtype=np.uint8), np.array([180, 120, 255], dtype=np.uint8))
                    mask = cv2.resize(mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                    variants["white_text"] = cv2.copyMakeBorder(cv2.bitwise_not(mask), 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255)

            output_dir = self._image_path.parent / f"ocr_debug_{self._image_path.stem}"
            if save_files_checkbox.isChecked():
                output_dir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(output_dir / "00_original_crop.png"), bgr_image)
                (output_dir / "results.txt").write_text(
                    f"Image: {self._image_path}\n"
                    f"RECT: ({left}, {top}, {right}, {bottom})\n"
                    f"Language: vie+eng; scale: {scale}; PSM: {selected_psms}\n"
                    f"Steps: {selected_steps}\n"
                    f"Text RGB: {text_rgb}; background RGB: {background_rgb}; "
                    f"border RGB: {border_rgb}; output background RGB: {output_background_rgb}; "
                    f"color tolerance: {tolerance_input.value()}\n\n",
                    encoding="utf-8",
                )

            if not variants:
                QMessageBox.warning(self, "Chưa có step hợp lệ", "Không tạo được ảnh xử lý từ các steps đã chọn.")
                return

            grouped_candidates = []
            total_jobs = len(variants) * len(selected_psms)
            progress = QProgressDialog("Đang khởi tạo OCR...", "Hủy", 0, total_jobs, self)
            progress.setWindowTitle("Đang phân tích OCR")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.show()
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            completed_jobs = 0
            print(
                f"[OCR] Có {len(variants)} step và {len(selected_psms)} PSM; "
                f"tổng cộng {total_jobs} lượt OCR.",
                flush=True,
            )
            for variant_name, processed in variants.items():
                if progress.wasCanceled():
                    break
                if save_files_checkbox.isChecked():
                    image_to_save = (
                        cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
                        if processed.ndim == 3 else processed
                    )
                    cv2.imwrite(str(output_dir / f"{self._image_path.stem}.{variant_name}.png"), image_to_save)
                for psm in selected_psms:
                    if progress.wasCanceled():
                        break
                    progress.setLabelText(f"Đang OCR: {variant_name} / PSM {psm} ({completed_jobs + 1}/{total_jobs})")
                    print(
                        f"[OCR] ({completed_jobs + 1}/{total_jobs}) Bắt đầu step={variant_name}, PSM={psm}",
                        flush=True,
                    )
                    QApplication.processEvents()
                    try:
                        data = pytesseract.image_to_data(
                            processed, lang="vie+eng", config=f"--oem 3 --psm {psm}",
                            output_type=pytesseract.Output.DICT,
                        )
                    except pytesseract.TesseractError as first_error:
                        print(
                            f"[OCR] Cảnh báo: vie+eng thất bại ở {variant_name}/PSM {psm}: {first_error}; thử eng.",
                            flush=True,
                        )
                        data = pytesseract.image_to_data(
                            processed, lang="eng", config=f"--oem 3 --psm {psm}",
                            output_type=pytesseract.Output.DICT,
                        )
                    recognized_words = [
                        str(raw).strip() for raw in data.get("text", []) if str(raw).strip()
                    ]
                    normalized_words = [
                        self.normalize_text(word) for word in recognized_words
                    ]
                    normalized_words = [word for word in normalized_words if word]
                    print(
                        f"[OCR] ({completed_jobs + 1}/{total_jobs}) Hoàn tất step={variant_name}, "
                        f"PSM={psm}, số từ nhận diện={len(recognized_words)}: "
                        f"{' '.join(normalized_words)[:500]}",
                        flush=True,
                    )
                    # Log each recognized text line with its rectangle in original-image pixels.
                    for line_item in self._split_ocr_words(data, min_confidence=45.0):
                        normalized_line = self.normalize_text(line_item["text"])
                        if not normalized_line:
                            continue
                        x = max(left, left + round((line_item["left"] - 18) / scale))
                        y = max(top, top + round((line_item["top"] - 18) / scale))
                        right_x = min(right, left + round((line_item["right"] - 18) / scale))
                        bottom_y = min(bottom, top + round((line_item["bottom"] - 18) / scale))
                        width_px = max(0, right_x - x)
                        height_px = max(0, bottom_y - y)
                        print(
                            f"[OCR]   {normalized_line} ({x}; {y}; {width_px}; {height_px})",
                            flush=True,
                        )
                    if save_files_checkbox.isChecked():
                        words = []
                        confidences = []
                        for i, raw_text in enumerate(data["text"]):
                            word = raw_text.strip()
                            try:
                                confidence = float(data["conf"][i])
                            except (ValueError, TypeError):
                                confidence = -1
                            if word and confidence >= 0:
                                words.append(word)
                                confidences.append(confidence)
                        recognized = " ".join(words)
                        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                        with (output_dir / "results.txt").open("a", encoding="utf-8") as summary:
                            normalized_recognized = self.normalize_text(recognized)
                            summary.write(
                                f"[{variant_name} | PSM {psm}] confidence trung bình: {avg_conf:.1f}\n"
                                f"Text gốc: {recognized or '(không nhận diện được chữ)'}\n"
                                f"Chuẩn hóa: {normalized_recognized or '(không có text)'}\n\n"
                            )
                        csv_path = output_dir / f"{self._image_path.stem}.{variant_name}.psm{psm}.csv"
                        with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                            writer = csv.writer(csv_file)
                            writer.writerow([
                                "text", "confidence", "left_processed", "top_processed",
                                "width_processed", "height_processed",
                            ])
                            for i, raw_text in enumerate(data["text"]):
                                word = raw_text.strip()
                                if not word:
                                    continue
                                writer.writerow([
                                    word, data["conf"][i], data["left"][i], data["top"][i],
                                    data["width"][i], data["height"][i],
                                ])
                        annotated = (
                            cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
                            if processed.ndim == 3 else cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
                        )
                        for i, raw_text in enumerate(data["text"]):
                            if not raw_text.strip():
                                continue
                            x, y = int(data["left"][i]), int(data["top"][i])
                            w, h = int(data["width"][i]), int(data["height"][i])
                            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 180, 0), 1)
                        cv2.imwrite(
                            str(output_dir / f"{self._image_path.stem}.{variant_name}.psm{psm}.boxes.png"),
                            annotated,
                        )
                    for item in self._split_ocr_words(data, min_confidence=45.0):
                        # Combine results from selected steps/PSMs and remove duplicate boxes below.
                        grouped_candidates.append(item)
                    completed_jobs += 1
                    progress.setValue(completed_jobs)
                    QApplication.processEvents()
            progress.close()
            if completed_jobs == 0:
                print("[OCR] Đã hủy phân tích trước khi hoàn thành lượt OCR nào.", flush=True)
                self.instruction.setText("Đã hủy phân tích OCR.")
                return

            unique_candidates = []
            seen_candidates = set()
            for item in sorted(grouped_candidates, key=lambda x: x["confidence"], reverse=True):
                signature = (self.normalize_text(item["text"]), round(item["left"] / scale), round(item["top"] / scale))
                if signature in seen_candidates:
                    continue
                seen_candidates.add(signature)
                unique_candidates.append(item)
            grouped = sorted(unique_candidates, key=lambda x: (x["top"], x["left"]))
            self._ocr_elements = []
            self.image_view.set_ocr_boxes([])
            image_width, image_height = original_size

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
                self._ocr_elements.append({
                    "name": self.normalize_text(item["text"]),
                    "text": item["text"],
                    "confidence": item["confidence"],
                    "word_bounds": [],
                    "bounds": {"left": x1, "top": y1, "right": x2, "bottom": y2},
                    "rect": {"x": x1, "y": y1, "width": width, "height": height},
                    "center": {"x_px": center_x, "y_px": center_y},
                    "center_ratio": {"x": round(center_x / image_width, 6), "y": round(center_y / image_height, 6)},
                    "bounds_ratio": {
                        "left": round(x1 / image_width, 6), "top": round(y1 / image_height, 6),
                        "right": round(x2 / image_width, 6), "bottom": round(y2 / image_height, 6),
                    },
                })
            self.image_view.set_ocr_boxes(self._ocr_elements)
            matches = [
                item for item in self._ocr_elements
                if not target_normalized or target_normalized in item["name"]
            ]
            if target_normalized:
                for item in self._ocr_elements:
                    item["matched"] = target_normalized in item["name"]
                self.image_view.set_ocr_boxes(self._ocr_elements)
            saved_message = (
                f" File debug đã lưu tại: {output_dir}"
                if save_files_checkbox.isChecked() else ""
            )
            print(
                f"[OCR] Hoàn tất: {len(matches)} dòng khớp / {len(self._ocr_elements)} dòng nhận diện; "
                f"hoàn thành {completed_jobs}/{total_jobs} lượt.",
                flush=True,
            )
            self.instruction.setText(
                f"OCR hoàn tất: {len(matches)} dòng khớp / {len(self._ocr_elements)} dòng nhận diện. "
                f"Steps={', '.join(selected_steps)}; PSM={', '.join(map(str, selected_psms))}. "
                "Nhấp vào hộp chữ để chọn tọa độ." + saved_message
            )
        except Exception as exc:
            import traceback
            print(f"[OCR] LỖI: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
            QMessageBox.critical(self, "Lỗi OCR", f"Không thể phân tích OCR: {exc}")

    def undo_point(self) -> None:
        if self._points:
            self._points.pop()
            self.image_view.set_points(self._points)
            self.instruction.setText(f"Còn {len(self._points)} điểm đã chọn.")

    def clear_points(self) -> None:
        """Reset all annotations on the current image, including RECT and OCR results."""
        self._points.clear()
        self._ocr_elements = []
        self._ocr_region = None
        self.image_view.set_points(self._points)
        self.image_view.set_ocr_boxes([])
        self.image_view.set_selected_region(None)
        self._on_mode_changed(self._current_mode())
        self.instruction.setText("Đã làm mới: xóa toàn bộ điểm, RECT và kết quả OCR.")

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
                data = self._remove_corner_metadata(data)
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
                data = self._remove_corner_metadata(
                    self._read_json(REGIONS_PATH, {"regions": {}})
                )
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
    def _remove_corner_metadata(value):
        """Remove legacy manual corner-coordinate fields from nested saved JSON."""
        corner_keys = {
            "manual_top_left", "manual_top_right",
            "manual_bottom_left", "manual_bottom_right",
            "top_left", "top_right", "bottom_left", "bottom_right",
            "corners", "corners_order",
        }
        if isinstance(value, dict):
            for key in list(value):
                if key in corner_keys:
                    del value[key]
                else:
                    ScreenshotAnnotator._remove_corner_metadata(value[key])
        elif isinstance(value, list):
            for item in value:
                ScreenshotAnnotator._remove_corner_metadata(item)
        return value

    @staticmethod
    def _read_json(path: Path, default: dict) -> dict:
        if not path.exists():
            return default
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"File JSON không phải object: {path}")
        return data
