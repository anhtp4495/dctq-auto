"""Dialog chụp màn hình ADB và đánh dấu tọa độ trên ảnh gốc."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


from PySide6.QtCore import QPoint, Qt, QSettings, QTimer
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
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
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.adb.client import AdbClient


LOCATIONS_PATH = Path("dctq_auto/tasks/common/locations.json")
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
        self._strategy_active_segment: int | None = None
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
        self._strategy_active_segment = None
        self.update()

    def set_strategy_active_segment(self, index: int | None, segment: int | None) -> None:
        self._strategy_active_step = index
        self._strategy_active_segment = segment
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
                    elif step.get("type") == "swipe_path":
                        points = step.get("points", [])
                        for segment_index in range(max(0, len(points) - 1)):
                            source = points[segment_index]
                            destination = points[segment_index + 1]
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
                            is_active_segment = (
                                is_active and self._strategy_active_segment == segment_index
                            )
                            segment_pen = QPen(
                                Qt.GlobalColor.yellow if is_active_segment else Qt.GlobalColor.cyan
                            )
                            segment_pen.setWidth(6 if is_active_segment else 3)
                            painter.setPen(segment_pen)
                            painter.drawLine(start, end)
                        painter.setPen(pen)
                        for point_index, point in enumerate(points, start=1):
                            if len(point) != 2:
                                continue
                            vertex = QPoint(
                                target.x() + round(int(point[0]) * scale_x),
                                target.y() + round(int(point[1]) * scale_y),
                            )
                            painter.drawEllipse(vertex, 6, 6)
                            painter.drawText(vertex.x() + 8, vertex.y() - 8, str(point_index))
                        if points and len(points[0]) == 2:
                            first = QPoint(
                                target.x() + round(int(points[0][0]) * scale_x),
                                target.y() + round(int(points[0][1]) * scale_y),
                            )
                            painter.drawText(first.x() + 9, first.y() + 18, f"P{index}")
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
        self, serial: str | None, parent=None, on_location_result=None,
        initial_image: Path | None = None,
    ) -> None:
        super().__init__(parent)
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
        self._strategy_root = (
            Path(__file__).resolve().parents[1]
            / "tasks"
            / "common"
            / "battle"
            / "battle_strategies"
        )
        self._strategy_dirs = {
            "state_war": self._strategy_root / "state_war",
            "ranked": self._strategy_root / "ranked",
        }
        self._strategy_dir = self._strategy_dirs["state_war"]
        self._strategy_path: Path | None = None
        self._strategy_steps: list[dict] = []
        self._strategy_path_points: list[list[int]] = []
        self._strategy_editing_index = -1
        self._strategy_capture_target: str | None = None
        self._strategy_preview_index = -1
        self._strategy_preview_segment = 0
        self._strategy_preview_repeat = 1
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
            (self.region_mode_button, "Từng vùng: kéo chọn vùng RECT để lưu tọa độ"),
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
        self.clear_button.setToolTip("Xóa toàn bộ điểm và RECT đã chọn trên ảnh.")
        self.clear_button.clicked.connect(self.clear_points)
        bottom.addWidget(self.clear_button)
        self.undo_button = QPushButton("↩️ Bỏ điểm cuối")
        self.undo_button.clicked.connect(self.undo_point)
        bottom.addWidget(self.undo_button)
        self.save_button = QPushButton("💾 Lưu file")
        self.save_button.clicked.connect(self.save_coordinates)
        bottom.addWidget(self.save_button)
        self._on_mode_changed(self._current_mode())
        root.addLayout(bottom)

        if initial_image is not None and initial_image.is_file():
            self._load_screenshot(initial_image)

    def _build_strategy_editor(self, root: QVBoxLayout) -> None:
        """Add a compact strategy JSON editor above the existing image analyzer."""
        group = QGroupBox("Biên tập chiến thuật")
        layout = QVBoxLayout(group)

        file_row = QHBoxLayout()
        self.strategy_category_combo = QComboBox()
        self.strategy_category_combo.addItem("Quốc chiến", "state_war")
        self.strategy_category_combo.addItem("Tranh Bá", "ranked")
        self.strategy_category_combo.currentIndexChanged.connect(
            self._on_strategy_category_changed
        )
        file_row.addWidget(self.strategy_category_combo)
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
        self.strategy_type_combo.addItem("None", "none")
        self.strategy_type_combo.addItem("Click", "click")
        self.strategy_type_combo.addItem("Swipe", "swipe")
        self.strategy_type_combo.addItem("Swipe Path", "swipe_path")
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
        self.strategy_repeat = self._strategy_spin(minimum=1, maximum=1000)
        self.strategy_path_points_label = QLabel("Chưa có điểm")
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
        fields.addWidget(QLabel("Số vòng"), 6, 0)
        fields.addWidget(self.strategy_repeat, 6, 1)
        fields.addWidget(QLabel("Điểm đường"), 6, 2)
        fields.addWidget(self.strategy_path_points_label, 6, 3)
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
        path_actions = QHBoxLayout()
        self.strategy_capture_path_button = QPushButton("Vẽ Swipe Path")
        self.strategy_capture_path_button.setCheckable(True)
        self.strategy_capture_path_button.clicked.connect(self._toggle_strategy_path_capture)
        path_actions.addWidget(self.strategy_capture_path_button)
        self.strategy_clear_path_button = QPushButton("Xóa điểm đường")
        self.strategy_clear_path_button.clicked.connect(self._clear_strategy_path_points)
        path_actions.addWidget(self.strategy_clear_path_button)
        path_actions.addStretch(1)
        layout.addLayout(path_actions)
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
            "Lần lượt làm nổi bật click, swipe và từng cạnh của swipe path ngay trên ảnh; "
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

    def _on_strategy_category_changed(self, _index: int) -> None:
        category = self.strategy_category_combo.currentData()
        self._strategy_dir = self._strategy_dirs.get(category, self._strategy_dirs["state_war"])
        self._strategy_path = None
        self._strategy_steps = []
        self._refresh_strategy_files()

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
        elif step.get("type") == "swipe_path":
            coordinate = f"{len(step.get('points', []))} điểm, lặp {step.get('repeat', 1)} vòng"
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
        self._strategy_path_points = []
        self.strategy_path_points_label.setText("0 điểm")
        self.strategy_repeat.setValue(1)
        for spin in (
            self.strategy_x, self.strategy_y, self.strategy_from_x, self.strategy_from_y,
            self.strategy_to_x, self.strategy_to_y, self.strategy_delay,
        ):
            spin.setValue(0)
        self.strategy_duration.setValue(300)
        self._update_strategy_field_visibility()

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
        self._strategy_path_points = [
            [int(point[0]), int(point[1])]
            for point in step.get("points", [])
            if isinstance(point, list) and len(point) == 2
        ]
        self.strategy_repeat.setValue(int(step.get("repeat", 1)))
        self.strategy_path_points_label.setText(
            f"{len(self._strategy_path_points)} điểm"
        )
        self._strategy_editing_index = index
        self._update_strategy_field_visibility()
        self._refresh_strategy_overlay()

    def _update_strategy_field_visibility(self, *_args) -> None:
        action = self.strategy_type_combo.currentData()
        is_none = action == "none"
        is_click = action == "click"
        is_swipe = action == "swipe"
        is_path = action == "swipe_path"
        if not is_path and self._strategy_capture_target == "swipe_path":
            self._strategy_capture_target = None
        for widget in (self.strategy_x, self.strategy_y):
            widget.setEnabled(is_click)
        for widget in (
            self.strategy_from_x, self.strategy_from_y,
            self.strategy_to_x, self.strategy_to_y,
        ):
            widget.setEnabled(is_swipe)
        self.strategy_duration.setEnabled(is_swipe or is_path)
        self.strategy_repeat.setEnabled(is_path)
        self.strategy_path_points_label.setEnabled(is_path)
        self.strategy_capture_click_button.setEnabled(is_click)
        self.strategy_capture_from_button.setEnabled(is_swipe)
        self.strategy_capture_to_button.setEnabled(is_swipe)
        self.strategy_capture_swipe_button.setEnabled(is_swipe)
        self.strategy_capture_path_button.setEnabled(is_path)
        is_capturing_path = self._strategy_capture_target == "swipe_path"
        self.strategy_capture_path_button.setEnabled(is_path)
        self.strategy_capture_path_button.blockSignals(True)
        self.strategy_capture_path_button.setChecked(is_capturing_path)
        self.strategy_capture_path_button.setText(
            f"Kết thúc vẽ ({len(self._strategy_path_points)} điểm)"
            if is_capturing_path else "Vẽ Swipe Path"
        )
        self.strategy_capture_path_button.blockSignals(False)
        self.strategy_clear_path_button.setEnabled(is_path and bool(self._strategy_path_points))

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
            "swipe_path": "đường vuốt đa giác",
        }
        if target == "swipe_path":
            self._strategy_path_points = []
            self.strategy_path_points_label.setText("0 điểm")
            instruction = "Nhấp lần lượt các đỉnh trên ảnh; nhấn nút Vẽ Swipe Path lần nữa để kết thúc."
        else:
            instruction = (
                "Kéo chuột từ điểm đầu đến điểm cuối ngay trên ảnh."
                if target == "swipe"
                else "Nhấp vào vị trí tương ứng trên ảnh."
            )
        self._update_strategy_field_visibility()
        self._refresh_strategy_overlay(include_form=True)
        self.strategy_editor_status.setText(f"Đang chờ chọn {labels[target]}: {instruction}")

    def _toggle_strategy_path_capture(self, checked: bool) -> None:
        if checked:
            if self._pixmap.isNull():
                self.strategy_capture_path_button.blockSignals(True)
                self.strategy_capture_path_button.setChecked(False)
                self.strategy_capture_path_button.blockSignals(False)
                QMessageBox.information(
                    self, "Chưa có ảnh", "Hãy mở ảnh trước khi vẽ Swipe Path."
                )
                return
            self._begin_strategy_capture("swipe_path")
            return
        self._finish_strategy_path_capture()

    def _finish_strategy_path_capture(self) -> None:
        if self._strategy_capture_target != "swipe_path":
            return
        if len(self._strategy_path_points) < 2:
            # Keep capture active so the user can add the required second point.
            self.strategy_capture_path_button.blockSignals(True)
            self.strategy_capture_path_button.setChecked(True)
            self.strategy_capture_path_button.blockSignals(False)
            QMessageBox.information(
                self, "Chưa đủ điểm", "Đường vuốt cần ít nhất 2 điểm. Hãy chọn thêm đỉnh."
            )
            return
        self._strategy_capture_target = None
        self._update_strategy_field_visibility()
        self._refresh_strategy_overlay(include_form=True)
        self.strategy_editor_status.setText(
            f"Đã hoàn tất đường vuốt gồm {len(self._strategy_path_points)} điểm, "
            f"{len(self._strategy_path_points) - 1} cạnh. Nhấn Cập nhật để lưu thay đổi "
            "vào bước đang chọn hoặc Thêm bước để tạo bước mới."
        )

    def _clear_strategy_path_points(self) -> None:
        self._strategy_path_points = []
        self.strategy_path_points_label.setText("0 điểm")
        if self._strategy_capture_target == "swipe_path":
            self._strategy_capture_target = None
        self._update_strategy_field_visibility()
        self._refresh_strategy_overlay(include_form=True)
        self.strategy_editor_status.setText("Đã xóa các điểm của đường vuốt.")

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
        if target == "swipe_path":
            self._strategy_path_points.append([x, y])
            self.strategy_path_points_label.setText(
                f"{len(self._strategy_path_points)} điểm"
            )
            self._update_strategy_field_visibility()
            self.strategy_capture_path_button.setText(
                f"Kết thúc vẽ ({len(self._strategy_path_points)} điểm)"
            )
            self.strategy_editor_status.setText(
                f"Đã thêm điểm {len(self._strategy_path_points)}: ({x}, {y}). "
                "Nhấp tiếp để thêm đỉnh; nhấn nút Vẽ Swipe Path lần nữa để kết thúc."
            )
            self._refresh_strategy_overlay(include_form=True)
            return True
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
            if draft["type"] == "none":
                pass
            elif draft["type"] == "click":
                draft.update({"x": self.strategy_x.value(), "y": self.strategy_y.value()})
            elif draft["type"] == "swipe":
                draft.update({
                    "from": [self.strategy_from_x.value(), self.strategy_from_y.value()],
                    "to": [self.strategy_to_x.value(), self.strategy_to_y.value()],
                })
            else:
                draft.update({
                    "points": [list(point) for point in self._strategy_path_points],
                    "repeat": self.strategy_repeat.value(),
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
        self._strategy_preview_segment = 0
        self._strategy_preview_repeat = 1
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
        description = str(step.get("description") or f"Bước {index + 1}")
        if step.get("type") == "none":
            self.image_view.set_strategy_active_step(None)
            interval = max(0, int(step.get("delay", 0)))
            self.strategy_editor_status.setText(
                f"Xem trước bước {index + 1}/{len(self._strategy_steps)}: "
                f"{description} — None (không có điểm preview)"
            )
        elif step.get("type") == "click":
            self.image_view.set_strategy_active_step(index)
            coordinate = f"click ({step.get('x', 0)}, {step.get('y', 0)})"
            interval = max(0, int(step.get("delay", 0)))
            self.strategy_editor_status.setText(
                f"Xem trước bước {index + 1}/{len(self._strategy_steps)}: "
                f"{description} — {coordinate}"
            )
        elif step.get("type") == "swipe":
            self.image_view.set_strategy_active_step(index)
            coordinate = f"swipe {step.get('from', [])} → {step.get('to', [])}"
            interval = max(0, int(step.get("duration", 300)) + int(step.get("delay", 0)))
            self.strategy_editor_status.setText(
                f"Xem trước bước {index + 1}/{len(self._strategy_steps)}: "
                f"{description} — {coordinate}"
            )
        else:
            points = step.get("points", [])
            segment_count = len(points) - 1
            repeat = int(step.get("repeat", 1))
            segment_index = self._strategy_preview_segment
            if segment_index >= segment_count:
                self._strategy_preview_segment = 0
                self._strategy_preview_repeat += 1
                if self._strategy_preview_repeat > repeat:
                    self._strategy_preview_index += 1
                    self._strategy_preview_repeat = 1
                    self._show_strategy_preview_step()
                    return
                segment_index = 0
            self.image_view.set_strategy_active_segment(index, segment_index)
            start = points[segment_index]
            end = points[segment_index + 1]
            self.strategy_editor_status.setText(
                f"Xem trước bước {index + 1}/{len(self._strategy_steps)}: {description} — "
                f"cạnh {segment_index + 1}/{segment_count}, "
                f"vòng {self._strategy_preview_repeat}/{repeat}: {start} → {end}"
            )
            interval = max(0, int(step.get("duration", 300)) + int(step.get("delay", 0)))
        # Match the JSON timing: click delay, or swipe duration plus delay.
        self._strategy_preview_timer.start(interval)

    def _advance_strategy_preview(self) -> None:
        step = (
            self._strategy_steps[self._strategy_preview_index]
            if 0 <= self._strategy_preview_index < len(self._strategy_steps)
            else None
        )
        if step is not None and step.get("type") == "swipe_path":
            self._strategy_preview_segment += 1
        else:
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
        if step["type"] == "none":
            return step
        if step["type"] == "click":
            step.update({"x": self.strategy_x.value(), "y": self.strategy_y.value()})
        elif step["type"] == "swipe":
            step.update({
                "from": [self.strategy_from_x.value(), self.strategy_from_y.value()],
                "to": [self.strategy_to_x.value(), self.strategy_to_y.value()],
                "duration": self.strategy_duration.value(),
            })
        else:
            if len(self._strategy_path_points) < 2:
                raise ValueError("Swipe Path cần ít nhất 2 điểm. Hãy vẽ đường trên ảnh.")
            step.update({
                "points": [list(point) for point in self._strategy_path_points],
                "repeat": self.strategy_repeat.value(),
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
            from dctq_auto.tasks.common.battle.battle_strategies.custom_battle import _validate_step
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
        if mode == "Từng vùng":
            message = "Từng vùng: kéo chọn một vùng RECT để lấy tọa độ."
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
        self.image_view.set_selected_region(None)
        self.image_view._pixmap = self._pixmap
        self._apply_zoom()
        self.image_view.set_points(self._points)
        self._refresh_strategy_overlay()
        self.image_info.setText(
            f"{self._image_path} — ảnh gốc {self._pixmap.width()}×{self._pixmap.height()} px"
        )
        self.instruction.setText(
            "Đã mở ảnh. Chọn Từng điểm để lưu nhiều tọa độ hoặc Từng vùng để lấy tọa độ RECT."
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
            if is_point:
                self.point_mode_button.setChecked(True)
                self._on_mode_changed("Từng điểm")
                self._points = [(left, top, "manual_point")]
                self.image_view.set_points(self._points)
                self.instruction.setText(f"Đã nhập point: ({left}, {top}) trên ảnh gốc.")
                if self._on_location_result is not None:
                    self._on_location_result("Point nhập tay", "manual_point", left, top, left / image_width, top / image_height)
            else:
                right, bottom = values["right"], values["bottom"]
                self.region_mode_button.setChecked(True)
                self._on_mode_changed("Từng vùng")
                self._points = []
                self.image_view.set_points(self._points)
                self.image_view.set_selected_region((left, top, right, bottom))
                self.instruction.setText(f"Đã nhập RECT: top={top}, left={left}, right={right}, bottom={bottom}.")
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
        self._points = []
        self.image_view.set_points(self._points)
        self.image_view.set_selected_region((left, top, right, bottom))
        self.instruction.setText(f"Đã chọn RECT '{name}'.")
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




    def undo_point(self) -> None:
        if self._points:
            self._points.pop()
            self.image_view.set_points(self._points)
            self.instruction.setText(f"Còn {len(self._points)} điểm đã chọn.")

    def clear_points(self) -> None:
        """Reset all point and rectangle annotations on the current image."""
        self._points.clear()
        self.image_view.set_points(self._points)
        self.image_view.set_selected_region(None)
        self._on_mode_changed(self._current_mode())
        self.instruction.setText("Đã làm mới: xóa toàn bộ điểm và RECT.")

    def save_coordinates(self) -> None:
        if self._pixmap.isNull() or self._image_path is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Hãy chọn ảnh trong artifacts/screenshots trước.")
            return
        if not self._points:
            QMessageBox.warning(self, "Chưa có tọa độ", "Hãy nhấp chọn ít nhất một điểm trước.")
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

            parts = []
            if self._points:
                parts.append(f"{len(self._points)} tọa độ vào {LOCATIONS_PATH}")
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