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

from PySide6.QtCore import QPoint, Qt, QSettings, QTimer
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QScrollArea,
    QSlider,
    QSpinBox,
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
        is_swipe_capture=None,
        on_image_swipe=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self._on_image_click = on_image_click
        self._is_region_mode = is_region_mode
        self._on_image_rect = on_image_rect
        self._is_cursor_mode = is_cursor_mode or (lambda: False)
        self._is_swipe_capture = is_swipe_capture or (lambda: False)
        self._on_image_swipe = on_image_swipe or (lambda *_args: None)
        self._points: list[tuple[int, int, str]] = []
        self._strategy_steps: list[dict] = []
        self._strategy_active_step: int | None = None
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

    def set_strategy_steps(self, steps: list[dict]) -> None:
        self._strategy_steps = [dict(step) for step in steps]
        self.update()

    def set_strategy_active_step(self, index: int | None) -> None:
        self._strategy_active_step = index
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

            if self._strategy_steps:
                for index, step in enumerate(self._strategy_steps, start=1):
                    is_active = self._strategy_active_step == index - 1
                    pen = QPen(
                        Qt.GlobalColor.yellow if is_active else Qt.GlobalColor.cyan
                    )
                    pen.setWidth(5 if is_active else 3)
                    painter.setPen(pen)
                    if step.get("type") == "click":
                        px = target.x() + round(int(step.get("x", 0)) * scale_x)
                        py = target.y() + round(int(step.get("y", 0)) * scale_y)
                        painter.drawEllipse(QPoint(px, py), 7, 7)
                        painter.drawText(px + 9, py - 8, f"C{index}")
                    elif step.get("type") == "swipe":
                        source = step.get("from", [0, 0])
                        destination = step.get("to", [0, 0])
                        if len(source) != 2 or len(destination) != 2:
                            continue
                        start = QPoint(
                            target.x() + round(int(source[0]) * scale_x),
                            target.y() + round(int(source[1]) * scale_y),
                        )
                        end = QPoint(
                            target.x() + round(int(destination[0]) * scale_x),
                            target.y() + round(int(destination[1]) * scale_y),
                        )
                        painter.drawLine(start, end)
                        painter.drawEllipse(start, 6, 6)
                        painter.drawEllipse(end, 6, 6)
                        painter.drawText(start.x() + 8, start.y() - 8, f"S{index}")
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
            pen.setWidth(3)
            painter.setPen(pen)
            if self._is_swipe_capture():
                painter.drawLine(self._drag_start, self._drag_current)
                painter.drawEllipse(self._drag_start, 5, 5)
                painter.drawEllipse(self._drag_current, 5, 5)
            else:
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
        if self._is_swipe_capture():
            self._drag_start = point
            self._drag_current = point
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
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
        if self._is_swipe_capture():
            if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
                self._on_image_click(x1, y1)
            else:
                self._on_image_swipe(x1, y1, x2, y2)
            return
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
        self._strategy_dir = (
            Path(__file__).resolve().parents[1]
            / "tasks" / "common" / "state_war" / "battle_strategies"
        )
        self._strategy_path: Path | None = None
        self._strategy_steps: list[dict] = []
        self._strategy_editing_index = -1
        self._strategy_capture_target: str | None = None
        self._strategy_preview_index = -1
        self._strategy_preview_timer = QTimer(self)
        self._strategy_preview_timer.setSingleShot(True)
        self._strategy_preview_timer.timeout.connect(self._advance_strategy_preview)
        self._build_strategy_editor(root)

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
        self.coordinate_input_button.setToolTip("Nhập Top, Left, Right, Bottom theo pixel ảnh gốc")
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
            lambda: self._strategy_capture_target == "swipe",
            self._on_image_swipe_selected,
        )
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_view)
        self.image_view.set_scroll_area(self.scroll_area)
        root.addWidget(self.scroll_area, 1)
        self._refresh_strategy_overlay()

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

    def _build_strategy_editor(self, root: QVBoxLayout) -> None:
        """Add a compact strategy JSON editor above the existing image analyzer."""
        group = QGroupBox("Biên tập chiến thuật Quốc chiến")
        layout = QVBoxLayout(group)

        file_row = QHBoxLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumWidth(180)
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_selected)
        file_row.addWidget(self.strategy_combo, 1)
        new_button = QPushButton("Mới")
        new_button.clicked.connect(self._new_strategy)
        file_row.addWidget(new_button)
        save_button = QPushButton("Lưu chiến thuật")
        save_button.clicked.connect(self._save_strategy)
        file_row.addWidget(save_button)
        delete_button = QPushButton("Xóa file")
        delete_button.clicked.connect(self._delete_strategy)
        file_row.addWidget(delete_button)
        layout.addLayout(file_row)

        meta_row = QHBoxLayout()
        self.strategy_name_input = QLineEdit()
        self.strategy_name_input.setPlaceholderText("Tên hiển thị chiến thuật")
        self.strategy_description_input = QLineEdit()
        self.strategy_description_input.setPlaceholderText("Mô tả chiến thuật")
        meta_row.addWidget(self.strategy_name_input, 1)
        meta_row.addWidget(self.strategy_description_input, 2)
        layout.addLayout(meta_row)

        editor_row = QHBoxLayout()
        self.strategy_step_list = QListWidget()
        self.strategy_step_list.setMaximumHeight(116)
        self.strategy_step_list.currentRowChanged.connect(self._load_selected_strategy_step)
        editor_row.addWidget(self.strategy_step_list, 2)

        fields = QGridLayout()
        self.strategy_type_combo = QComboBox()
        self.strategy_type_combo.addItem("Click", "click")
        self.strategy_type_combo.addItem("Swipe", "swipe")
        self.strategy_type_combo.currentIndexChanged.connect(self._update_strategy_field_visibility)
        self.strategy_step_description = QLineEdit()
        self.strategy_step_description.setPlaceholderText("Mô tả thao tác")
        self.strategy_x = self._strategy_spin()
        self.strategy_y = self._strategy_spin()
        self.strategy_from_x = self._strategy_spin()
        self.strategy_from_y = self._strategy_spin()
        self.strategy_to_x = self._strategy_spin()
        self.strategy_to_y = self._strategy_spin()
        self.strategy_delay = self._strategy_spin(maximum=600000)
        self.strategy_duration = self._strategy_spin(minimum=1, maximum=60000)
        fields.addWidget(QLabel("Loại"), 0, 0)
        fields.addWidget(self.strategy_type_combo, 0, 1, 1, 3)
        fields.addWidget(QLabel("Mô tả"), 1, 0)
        fields.addWidget(self.strategy_step_description, 1, 1, 1, 3)
        fields.addWidget(QLabel("X / Y"), 2, 0)
        fields.addWidget(self.strategy_x, 2, 1)
        fields.addWidget(self.strategy_y, 2, 2)
        fields.addWidget(QLabel("Từ"), 3, 0)
        fields.addWidget(self.strategy_from_x, 3, 1)
        fields.addWidget(self.strategy_from_y, 3, 2)
        fields.addWidget(QLabel("Đến"), 4, 0)
        fields.addWidget(self.strategy_to_x, 4, 1)
        fields.addWidget(self.strategy_to_y, 4, 2)
        fields.addWidget(QLabel("Delay (ms)"), 5, 0)
        fields.addWidget(self.strategy_delay, 5, 1)
        fields.addWidget(QLabel("Duration (ms)"), 5, 2)
        fields.addWidget(self.strategy_duration, 5, 3)
        self._strategy_fields_grid = fields
        editor_row.addLayout(fields, 4)
        layout.addLayout(editor_row)

        actions = QHBoxLayout()
        self.strategy_capture_click_button = QPushButton("Lấy điểm click")
        self.strategy_capture_click_button.clicked.connect(
            lambda: self._begin_strategy_capture("click")
        )
        actions.addWidget(self.strategy_capture_click_button)
        self.strategy_capture_from_button = QPushButton("Lấy điểm đầu")
        self.strategy_capture_from_button.clicked.connect(
            lambda: self._begin_strategy_capture("from")
        )
        actions.addWidget(self.strategy_capture_from_button)
        self.strategy_capture_to_button = QPushButton("Lấy điểm cuối")
        self.strategy_capture_to_button.clicked.connect(
            lambda: self._begin_strategy_capture("to")
        )
        actions.addWidget(self.strategy_capture_to_button)
        self.strategy_capture_swipe_button = QPushButton("Vẽ swipe trên ảnh")
        self.strategy_capture_swipe_button.clicked.connect(
            lambda: self._begin_strategy_capture("swipe")
        )
        actions.addWidget(self.strategy_capture_swipe_button)
        add_button = QPushButton("Thêm bước")
        add_button.clicked.connect(self._add_strategy_step)
        actions.addWidget(add_button)
        update_button = QPushButton("Cập nhật")
        update_button.clicked.connect(self._update_strategy_step)
        actions.addWidget(update_button)
        remove_button = QPushButton("Xóa bước")
        remove_button.clicked.connect(self._remove_strategy_step)
        actions.addWidget(remove_button)
        up_button = QPushButton("↑")
        up_button.setFixedWidth(32)
        up_button.clicked.connect(lambda: self._move_strategy_step(-1))
        actions.addWidget(up_button)
        down_button = QPushButton("↓")
        down_button.setFixedWidth(32)
        down_button.clicked.connect(lambda: self._move_strategy_step(1))
        actions.addWidget(down_button)
        self.strategy_test_button = QPushButton("▶ Xem trước steps")
        self.strategy_test_button.setToolTip(
            "Lần lượt làm nổi bật các tọa độ click/swipe ngay trên ảnh hiện tại; "
            "không gửi thao tác đến LDPlayer và không sử dụng ADB."
        )
        self.strategy_test_button.clicked.connect(self._preview_strategy_steps)
        actions.addWidget(self.strategy_test_button)
        layout.addLayout(actions)

        self.strategy_editor_status = QLabel(
            "Chọn chiến thuật hoặc nhấn Mới. Nhấn Lấy điểm rồi nhấp trực tiếp lên ảnh."
        )
        self.strategy_editor_status.setWordWrap(True)
        layout.addWidget(self.strategy_editor_status)
        root.addWidget(group)
        self._update_strategy_field_visibility()
        self._refresh_strategy_files()

    @staticmethod
    def _strategy_spin(minimum: int = 0, maximum: int = 100000) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setKeyboardTracking(False)
        return spin

    def _refresh_strategy_files(self, select_path: Path | None = None) -> None:
        self._strategy_dir.mkdir(parents=True, exist_ok=True)
        self.strategy_combo.blockSignals(True)
        self.strategy_combo.clear()
        for path in sorted(self._strategy_dir.glob("*.json"), key=lambda p: p.name.casefold()):
            self.strategy_combo.addItem(path.stem, str(path.resolve()))
        self.strategy_combo.blockSignals(False)
        selected = -1
        if select_path is not None:
            target = select_path.resolve()
            for index in range(self.strategy_combo.count()):
                if Path(self.strategy_combo.itemData(index)).resolve() == target:
                    selected = index
                    break
        if selected < 0 and self.strategy_combo.count():
            selected = 0
        if selected >= 0:
            self.strategy_combo.setCurrentIndex(selected)
            self._load_strategy_file(Path(self.strategy_combo.itemData(selected)))
        else:
            self._strategy_path = None
            self._strategy_steps = []
            self._render_strategy_steps()

    def _on_strategy_selected(self, index: int) -> None:
        if index < 0:
            return
        raw_path = self.strategy_combo.itemData(index)
        if raw_path:
            self._load_strategy_file(Path(raw_path))

    def _load_strategy_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            resolved.relative_to(self._strategy_dir.resolve())
            data = json.loads(resolved.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
                raise ValueError("JSON phải là object và có danh sách steps.")
            if any(not isinstance(step, dict) for step in data["steps"]):
                raise ValueError("Mỗi phần tử trong steps phải là object.")
            self._strategy_steps = [dict(step) for step in data["steps"]]
            self._strategy_path = resolved
            self.strategy_name_input.setText(
                str(data.get("display_name") or data.get("name") or resolved.stem)
            )
            self.strategy_description_input.setText(str(data.get("description") or ""))
            self._render_strategy_steps()
            self.strategy_editor_status.setText(
                f"Đã tải {resolved.name}: {len(self._strategy_steps)} bước."
            )
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Không đọc được chiến thuật", str(exc))

    def _new_strategy(self) -> None:
        name, accepted = QInputDialog.getText(
            self, "Chiến thuật mới", "Tên file (không dấu, không khoảng trắng):"
        )
        if not accepted:
            return
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip()).strip("_-").lower()
        if not slug:
            QMessageBox.warning(self, "Tên không hợp lệ", "Hãy nhập tên file hợp lệ.")
            return
        path = self._strategy_dir / f"{slug}.json"
        if path.exists():
            QMessageBox.warning(self, "File đã tồn tại", f"{path.name} đã tồn tại.")
            return
        self._strategy_path = path
        self._strategy_steps = []
        self.strategy_name_input.setText(name.strip())
        self.strategy_description_input.clear()
        self._render_strategy_steps()
        self.strategy_editor_status.setText(
            f"Đang tạo {path.name}. Thêm ít nhất một bước rồi lưu chiến thuật."
        )

    @staticmethod
    def _strategy_step_label(index: int, step: dict) -> str:
        description = str(step.get("description") or "").strip()
        action = str(step.get("type") or "?").upper()
        if step.get("type") == "click":
            coordinate = f"({step.get('x', 0)}, {step.get('y', 0)})"
        elif step.get("type") == "swipe":
            coordinate = f"{step.get('from', [])} → {step.get('to', [])}"
        else:
            coordinate = ""
        return f"{index}. [{action}] {description or 'Chưa mô tả'} {coordinate}"

    def _render_strategy_steps(self) -> None:
        # Rebuild the list without firing selection handlers halfway through.
        self.strategy_step_list.blockSignals(True)
        self.strategy_step_list.clear()
        for index, step in enumerate(self._strategy_steps, start=1):
            self.strategy_step_list.addItem(
                QListWidgetItem(self._strategy_step_label(index, step))
            )
        if self._strategy_steps:
            self.strategy_step_list.setCurrentRow(0)
        self.strategy_step_list.blockSignals(False)
        self._strategy_editing_index = -1
        if self._strategy_steps:
            self._load_selected_strategy_step(self.strategy_step_list.currentRow())
        else:
            self._clear_strategy_step_fields()
        self._refresh_strategy_overlay()

    def _clear_strategy_step_fields(self) -> None:
        self.strategy_type_combo.setCurrentIndex(0)
        self.strategy_step_description.clear()
        for spin in (
            self.strategy_x, self.strategy_y, self.strategy_from_x, self.strategy_from_y,
            self.strategy_to_x, self.strategy_to_y, self.strategy_delay,
        ):
            spin.setValue(0)
        self.strategy_duration.setValue(300)

    def _store_strategy_step_from_fields(self, index: int) -> None:
        if not (0 <= index < len(self._strategy_steps)):
            return
        updated = self._strategy_step_from_fields()
        self._strategy_steps[index] = updated
        item = self.strategy_step_list.item(index)
        if item is not None:
            item.setText(self._strategy_step_label(index + 1, updated))
        self._refresh_strategy_overlay()

    def _load_selected_strategy_step(self, index: int) -> None:
        previous_index = getattr(self, "_strategy_editing_index", -1)
        if previous_index == index:
            return

        # Commit the step being edited before loading another one.
        if 0 <= previous_index < len(self._strategy_steps):
            try:
                self._store_strategy_step_from_fields(previous_index)
            except ValueError as exc:
                self.strategy_step_list.blockSignals(True)
                self.strategy_step_list.setCurrentRow(previous_index)
                self.strategy_step_list.blockSignals(False)
                QMessageBox.warning(self, "Bước chưa hợp lệ", str(exc))
                return

        if not (0 <= index < len(self._strategy_steps)):
            self._strategy_editing_index = -1
            return

        step = self._strategy_steps[index]
        self.strategy_type_combo.setCurrentIndex(
            max(0, self.strategy_type_combo.findData(step.get("type", "click")))
        )
        self.strategy_step_description.setText(str(step.get("description") or ""))
        self.strategy_delay.setValue(int(step.get("delay", 0)))
        self.strategy_duration.setValue(int(step.get("duration", 300)))
        self.strategy_x.setValue(int(step.get("x", 0)))
        self.strategy_y.setValue(int(step.get("y", 0)))
        source = step.get("from", [0, 0])
        target = step.get("to", [0, 0])
        self.strategy_from_x.setValue(int(source[0]) if len(source) == 2 else 0)
        self.strategy_from_y.setValue(int(source[1]) if len(source) == 2 else 0)
        self.strategy_to_x.setValue(int(target[0]) if len(target) == 2 else 0)
        self.strategy_to_y.setValue(int(target[1]) if len(target) == 2 else 0)
        self._strategy_editing_index = index
        self._update_strategy_field_visibility()

    def _update_strategy_field_visibility(self, *_args) -> None:
        is_click = self.strategy_type_combo.currentData() == "click"
        for widget in (self.strategy_x, self.strategy_y):
            widget.setEnabled(is_click)
        for widget in (
            self.strategy_from_x, self.strategy_from_y,
            self.strategy_to_x, self.strategy_to_y, self.strategy_duration,
        ):
            widget.setEnabled(not is_click)
        self.strategy_capture_click_button.setEnabled(is_click)
        self.strategy_capture_from_button.setEnabled(not is_click)
        self.strategy_capture_to_button.setEnabled(not is_click)
        self.strategy_capture_swipe_button.setEnabled(not is_click)

    def _begin_strategy_capture(self, target: str) -> None:
        if self._pixmap.isNull():
            QMessageBox.information(self, "Chưa có ảnh", "Hãy mở ảnh trước khi lấy tọa độ.")
            return
        self._strategy_capture_target = target
        self.point_mode_button.setChecked(True)
        self._on_mode_changed("Từng điểm")
        labels = {
            "click": "tọa độ click",
            "from": "điểm đầu swipe",
            "to": "điểm cuối swipe",
            "swipe": "đường swipe",
        }
        instruction = (
            "Kéo chuột từ điểm đầu đến điểm cuối ngay trên ảnh."
            if target == "swipe"
            else "Nhấp vào vị trí tương ứng trên ảnh."
        )
        self.strategy_editor_status.setText(f"Đang chờ chọn {labels[target]}: {instruction}")

    def _on_image_swipe_selected(self, from_x: int, from_y: int, to_x: int, to_y: int) -> None:
        """Fill both swipe endpoints from a drag gesture on the screenshot."""
        if self.strategy_type_combo.currentData() != "swipe":
            return
        self.strategy_from_x.setValue(from_x)
        self.strategy_from_y.setValue(from_y)
        self.strategy_to_x.setValue(to_x)
        self.strategy_to_y.setValue(to_y)
        self._strategy_capture_target = None
        self.strategy_editor_status.setText(
            f"Đã lấy swipe: ({from_x}, {from_y}) → ({to_x}, {to_y}). "
            "Nhấn Cập nhật để áp dụng vào bước đang chọn hoặc Thêm bước để tạo bước mới."
        )
        self._refresh_strategy_overlay(include_form=True)

    def _capture_strategy_coordinate(self, x: int, y: int) -> bool:
        target = self._strategy_capture_target
        if target is None:
            return False
        self._strategy_capture_target = None
        if target == "click":
            self.strategy_x.setValue(x)
            self.strategy_y.setValue(y)
        elif target == "from":
            self.strategy_from_x.setValue(x)
            self.strategy_from_y.setValue(y)
        elif target == "to":
            self.strategy_to_x.setValue(x)
            self.strategy_to_y.setValue(y)
        self.strategy_editor_status.setText(
            f"Đã lấy tọa độ ảnh gốc: ({x}, {y}). Nhấn Thêm bước hoặc Cập nhật."
        )
        self._refresh_strategy_overlay(include_form=True)
        return True

    def _refresh_strategy_overlay(self, include_form: bool = False) -> None:
        """Show saved-in-editor steps and the currently edited draft on the screenshot."""
        overlay = [dict(step) for step in self._strategy_steps]
        if include_form:
            draft = {
                "type": self.strategy_type_combo.currentData(),
                "description": self.strategy_step_description.text().strip() or "Bản nháp",
            }
            if draft["type"] == "click":
                draft.update({"x": self.strategy_x.value(), "y": self.strategy_y.value()})
            else:
                draft.update({
                    "from": [self.strategy_from_x.value(), self.strategy_from_y.value()],
                    "to": [self.strategy_to_x.value(), self.strategy_to_y.value()],
                })
            selected = self.strategy_step_list.currentRow()
            if 0 <= selected < len(overlay):
                overlay[selected] = draft
            else:
                overlay.append(draft)
        if hasattr(self, "image_view"):
            self.image_view.set_strategy_steps(overlay)

    def _preview_strategy_steps(self) -> None:
        """Preview strategy steps by highlighting coordinates on the loaded screenshot only."""
        if not self._strategy_steps:
            QMessageBox.information(self, "Chưa có steps", "Hãy thêm ít nhất một bước trước.")
            return
        if self._strategy_preview_timer.isActive():
            self._strategy_preview_timer.stop()
            self._strategy_preview_index = -1
            self.image_view.set_strategy_active_step(None)
            self.strategy_test_button.setText("▶ Xem trước steps")
            self.strategy_test_button.setEnabled(True)
            self.strategy_editor_status.setText("Đã dừng xem trước chiến thuật.")
            return

        self._strategy_preview_index = 0
        self.strategy_test_button.setText("■ Dừng xem trước")
        self.strategy_test_button.setEnabled(True)
        self._show_strategy_preview_step()

    def _show_strategy_preview_step(self) -> None:
        index = self._strategy_preview_index
        if not (0 <= index < len(self._strategy_steps)):
            self._strategy_preview_timer.stop()
            self._strategy_preview_index = -1
            self.image_view.set_strategy_active_step(None)
            self.strategy_test_button.setText("▶ Xem trước steps")
            self.strategy_editor_status.setText(
                f"Đã xem trước hoàn tất {len(self._strategy_steps)} bước. "
                "Không có thao tác nào được gửi đến LDPlayer."
            )
            return

        step = self._strategy_steps[index]
        self.image_view.set_strategy_active_step(index)
        description = str(step.get("description") or f"Bước {index + 1}")
        if step.get("type") == "click":
            coordinate = f"click ({step.get('x', 0)}, {step.get('y', 0)})"
        else:
            coordinate = f"swipe {step.get('from', [])} → {step.get('to', [])}"
        self.strategy_editor_status.setText(
            f"Xem trước bước {index + 1}/{len(self._strategy_steps)}: "
            f"{description} — {coordinate}"
        )
        # Keep each step visible long enough to inspect. Respect longer configured delays.
        interval = min(650, int(step.get("delay", 0)))
        self._strategy_preview_timer.start(interval)

    def _advance_strategy_preview(self) -> None:
        self._strategy_preview_index += 1
        self._show_strategy_preview_step()

    def _strategy_step_from_fields(self) -> dict:
        description = self.strategy_step_description.text().strip()
        if not description:
            raise ValueError("Mô tả bước không được để trống.")
        step = {
            "type": self.strategy_type_combo.currentData(),
            "delay": self.strategy_delay.value(),
            "description": description,
        }
        if step["type"] == "click":
            step.update({"x": self.strategy_x.value(), "y": self.strategy_y.value()})
        else:
            step.update({
                "from": [self.strategy_from_x.value(), self.strategy_from_y.value()],
                "to": [self.strategy_to_x.value(), self.strategy_to_y.value()],
                "duration": self.strategy_duration.value(),
            })
        return step

    def _add_strategy_step(self) -> None:
        try:
            self._strategy_steps.append(self._strategy_step_from_fields())
            self._render_strategy_steps()
            self.strategy_step_list.setCurrentRow(len(self._strategy_steps) - 1)
            self.strategy_editor_status.setText("Đã thêm bước. Nhớ lưu chiến thuật.")
        except ValueError as exc:
            QMessageBox.warning(self, "Thiếu thông tin", str(exc))

    def _update_strategy_step(self) -> None:
        index = self.strategy_step_list.currentRow()
        if not (0 <= index < len(self._strategy_steps)):
            QMessageBox.information(self, "Chưa chọn bước", "Hãy chọn bước cần cập nhật.")
            return
        try:
            self._strategy_steps[index] = self._strategy_step_from_fields()
            self._render_strategy_steps()
            self.strategy_step_list.setCurrentRow(index)
            self.strategy_editor_status.setText("Đã cập nhật bước. Nhớ lưu chiến thuật.")
        except ValueError as exc:
            QMessageBox.warning(self, "Thiếu thông tin", str(exc))

    def _remove_strategy_step(self) -> None:
        index = self.strategy_step_list.currentRow()
        if not (0 <= index < len(self._strategy_steps)):
            return
        self._strategy_steps.pop(index)
        self._render_strategy_steps()
        self.strategy_step_list.setCurrentRow(min(index, len(self._strategy_steps) - 1))
        self.strategy_editor_status.setText("Đã xóa bước. Nhớ lưu chiến thuật.")

    def _move_strategy_step(self, offset: int) -> None:
        index = self.strategy_step_list.currentRow()
        target = index + offset
        if not (0 <= index < len(self._strategy_steps) and 0 <= target < len(self._strategy_steps)):
            return
        self._strategy_steps[index], self._strategy_steps[target] = (
            self._strategy_steps[target], self._strategy_steps[index]
        )
        self._render_strategy_steps()
        self.strategy_step_list.setCurrentRow(target)
        self.strategy_editor_status.setText("Đã đổi thứ tự bước. Nhớ lưu chiến thuật.")

    def _save_strategy(self) -> None:
        if self._strategy_path is None:
            self._new_strategy()
            if self._strategy_path is None:
                return
        name = self.strategy_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Thiếu tên", "Hãy nhập tên hiển thị chiến thuật.")
            return

        # Save the values currently shown in the editor, even if the user did not
        # press "Cập nhật" first. This prevents the last edited step being lost.
        selected_index = self.strategy_step_list.currentRow()
        if 0 <= selected_index < len(self._strategy_steps):
            try:
                self._strategy_steps[selected_index] = self._strategy_step_from_fields()
            except ValueError as exc:
                QMessageBox.warning(self, "Bước chưa hợp lệ", str(exc))
                return

        if not self._strategy_steps:
            QMessageBox.warning(self, "Chưa có bước", "Chiến thuật cần ít nhất một bước.")
            return

        # Validate the same click/swipe schema used by the runtime executor.
        try:
            from dctq_auto.tasks.common.state_war.task_run_state_war import _validate_step
            steps = [_validate_step(step, index) for index, step in enumerate(self._strategy_steps, 1)]
        except (ImportError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Chiến thuật không hợp lệ", str(exc))
            return
        path = self._strategy_path.resolve()
        try:
            path.relative_to(self._strategy_dir.resolve())
            data = {
                "display_name": name,
                "description": self.strategy_description_input.text().strip(),
                "steps": steps,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._strategy_path = path
            self._refresh_strategy_files(select_path=path)
            self.strategy_editor_status.setText(f"Đã lưu {path.name} ({len(steps)} bước).")
            QMessageBox.information(self, "Đã lưu", f"Đã lưu chiến thuật vào:\n{path}")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Không lưu được", str(exc))

    def _delete_strategy(self) -> None:
        if self._strategy_path is None or not self._strategy_path.is_file():
            return
        answer = QMessageBox.question(
            self, "Xóa chiến thuật",
            f"Bạn chắc chắn muốn xóa {self._strategy_path.name}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._strategy_path.unlink()
            self._strategy_path = None
            self._strategy_steps = []
            self._refresh_strategy_files()
            self.strategy_editor_status.setText("Đã xóa file chiến thuật.")
        except OSError as exc:
            QMessageBox.critical(self, "Không xóa được", str(exc))

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
        """Allow selecting an image file from any directory."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh màn hình",
            str(Path.cwd()),
            "Ảnh màn hình (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not filename:
            return
        self._load_screenshot(Path(filename).resolve())

    def _load_screenshot(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Không mở được ảnh", f"Không đọc được file ảnh: {path}")
            return
        self._image_path = path
        self._pixmap = pixmap
        self._strategy_capture_target = None
        self._points.clear()
        self._ocr_elements = []
        self._ocr_region = None
        self.image_view.set_selected_region(None)
        self.image_view._pixmap = self._pixmap
        self._apply_zoom()
        self.image_view.set_points(self._points)
        self._refresh_strategy_overlay()
        self.image_view.set_ocr_boxes([])
        self.image_info.setText(
            f"{self._image_path} — ảnh gốc {self._pixmap.width()}×{self._pixmap.height()} px"
        )
        self.instruction.setText(
            "Đã mở ảnh. Chọn Từng điểm để lưu nhiều tọa độ hoặc Từng vùng để phân tích OCR một vùng."
        )
        self.image_view.update()

    def input_coordinates(self) -> None:
        """Open a validated Top/Left/Right/Bottom editor in original-image pixels."""
        if self._pixmap.isNull():
            QMessageBox.information(self, "Chưa có ảnh", "Hãy mở ảnh chụp màn hình trước.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Nhập vị trí")
        form = QFormLayout(dialog)
        top_input = QLineEdit()
        left_input = QLineEdit()
        right_input = QLineEdit()
        bottom_input = QLineEdit()
        for widget, placeholder in (
            (top_input, "Bắt buộc, từ 0 đến chiều cao ảnh - 1"),
            (left_input, "Bắt buộc, từ 0 đến chiều rộng ảnh - 1"),
            (right_input, "Để trống nếu nhập một điểm"),
            (bottom_input, "Để trống nếu nhập một điểm"),
        ):
            widget.setPlaceholderText(placeholder)
        form.addRow("Top:", top_input)
        form.addRow("Left:", left_input)
        form.addRow("Right:", right_input)
        form.addRow("Bottom:", bottom_input)
        hint = QLabel(
            f"Ảnh gốc: {self._pixmap.width()} × {self._pixmap.height()} px. "
            "Để nhập một điểm, để trống Right và Bottom; RECT cần đủ cả bốn cạnh."
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        form.addRow(buttons)

        fields = {"top": top_input, "left": left_input, "right": right_input, "bottom": bottom_input}

        def mark_invalid(names: set[str]) -> None:
            for name, widget in fields.items():
                widget.setStyleSheet(
                    "QLineEdit { border: 1px solid #dc2626; background: #fff1f2; }"
                    if name in names else ""
                )

        def accept_coordinates() -> None:
            invalid: set[str] = set()
            values: dict[str, int | None] = {}
            for name in ("top", "left", "right", "bottom"):
                raw = fields[name].text().strip()
                if not raw:
                    values[name] = None
                    continue
                try:
                    values[name] = int(raw)
                except ValueError:
                    values[name] = None
                    invalid.add(name)

            if values["top"] is None: invalid.add("top")
            if values["left"] is None: invalid.add("left")
            image_width, image_height = self._pixmap.width(), self._pixmap.height()
            if values["top"] is not None and not (0 <= values["top"] < image_height): invalid.add("top")
            if values["left"] is not None and not (0 <= values["left"] < image_width): invalid.add("left")
            right_empty = not right_input.text().strip()
            bottom_empty = not bottom_input.text().strip()
            is_point = right_empty and bottom_empty
            if right_empty != bottom_empty:
                invalid.update(("right", "bottom"))
            elif not is_point:
                if values["right"] is None or not (0 < values["right"] <= image_width): invalid.add("right")
                if values["bottom"] is None or not (0 < values["bottom"] <= image_height): invalid.add("bottom")
                if values["right"] is not None and values["left"] is not None and values["right"] <= values["left"]: invalid.add("right")
                if values["bottom"] is not None and values["top"] is not None and values["bottom"] <= values["top"]: invalid.add("bottom")

            mark_invalid(invalid)
            if invalid:
                hint.setText(
                    "Giá trị chưa hợp lệ: Top/Left phải nằm trong ảnh; Right phải lớn hơn Left; "
                    "Bottom phải lớn hơn Top và RECT phải nằm trong ảnh. Để nhập điểm, để trống Right và Bottom."
                )
                return

            top, left = values["top"], values["left"]
            self._ocr_elements = []
            self.image_view.set_ocr_boxes([])
            if is_point:
                self.point_mode_button.setChecked(True)
                self._on_mode_changed("Từng điểm")
                self._ocr_region = None
                self._points = [(left, top, "manual_point")]
                self.image_view.set_points(self._points)
                self.instruction.setText(f"Đã nhập point: ({left}, {top}) trên ảnh gốc.")
                if self._on_location_result is not None:
                    self._on_location_result("Point nhập tay", "manual_point", left, top, left / image_width, top / image_height)
            else:
                right, bottom = values["right"], values["bottom"]
                self.region_mode_button.setChecked(True)
                self._on_mode_changed("Từng vùng")
                self._ocr_region = (left, top, right, bottom)
                self._points = []
                self.image_view.set_points(self._points)
                self.image_view.set_selected_region(self._ocr_region)
                self.instruction.setText(f"Đã nhập RECT: top={top}, left={left}, right={right}, bottom={bottom}. Nhấn Phân tích OCR để nhận diện chữ trong vùng này.")
                if self._on_location_result is not None:
                    self._on_location_result("RECT nhập tay", "manual_rect", left, top, left / image_width, top / image_height)
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
        if self._capture_strategy_coordinate(x, y):
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
                f'"rect": {{ "top": {top}, "left": {left}, "right": {right}, "bottom": {bottom}}},',
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
        tolerance_input.setRange(1, 255)
        tolerance_input.setDecimals(1)
        tolerance_input.setValue(float(self._ui_settings.value("screenshot_annotator/ocr_tolerance", 38.0)))
        tolerance_input.setToolTip("Ngưỡng sai khác màu; dùng cho bước color_text và lọc viền.")
        form.addRow("Text cần phát hiện:", target_text_input)
        form.addRow("Text-color (#RRGGBB hoặc R,G,B):", text_color_row)
        form.addRow("Background-color:", background_color_row)
        form.addRow("Border-color (để trống nếu không có):", border_color_row)
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
        self._ui_settings.setValue("screenshot_annotator/ocr_tolerance", tolerance_input.value())
        self._ui_settings.setValue("screenshot_annotator/ocr_save_files", save_files_checkbox.isChecked())
        self._ui_settings.sync()

        print(
            "[OCR] Bắt đầu phân tích: "
            f"image={self._image_path}, rect={self._ocr_region}, "
            f"target={target_text!r}, steps={selected_steps}, psm={selected_psms}, "
            f"text_color={text_rgb}, background_color={background_rgb}, "
            f"border_color={border_rgb}, tolerance={tolerance_input.value()}, "
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
                    binary = np.where(mask, 0, 255).astype(np.uint8)
                    binary = cv2.resize(binary, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                    variants["color_text"] = cv2.copyMakeBorder(binary, 18, 18, 18, 18, cv2.BORDER_CONSTANT, value=255)
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
                    f"border RGB: {border_rgb}; color tolerance: {tolerance_input.value()}\n\n",
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
                    cv2.imwrite(str(output_dir / f"{self._image_path.stem}.{variant_name}.png"), processed)
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
                        annotated = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
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
