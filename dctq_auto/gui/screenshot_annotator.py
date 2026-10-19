"""Dialog chụp màn hình ADB và đánh dấu tọa độ trên ảnh gốc."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
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

    def __init__(self, serial: str | None, parent=None) -> None:
        super().__init__(parent)
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
        self.mode_combo.addItem("Chọn điểm ADB (mỗi lần nhấp đặt tên)", "point")
        self.mode_combo.addItem("Chọn vùng 4 góc để phân tích ảnh", "region")
        self.screen_name = QLineEdit("captured")
        self.screen_name.setToolTip("Tên màn hình lưu trong locations.json")
        self.point_name = QLineEdit("button")
        self.point_name.setToolTip("Tên gợi ý cho điểm kế tiếp")
        self.region_name = QLineEdit("analysis_region")
        settings.addRow("Chế độ:", self.mode_combo)
        settings.addRow("Tên màn hình:", self.screen_name)
        settings.addRow("Tên điểm tiếp theo:", self.point_name)
        settings.addRow("Tên vùng 4 góc:", self.region_name)
        root.addLayout(settings)

        self.instruction = QLabel("Chụp màn hình để bắt đầu.")
        self.instruction.setWordWrap(True)
        root.addWidget(self.instruction)

        self.image_view = ClickableImage(
            QPixmap(),
            self._on_image_click,
            lambda: self.mode_combo.currentData() == "region",
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
                "Chế độ điểm: nhấp để chọn tọa độ. Chế độ vùng 4 góc: kéo chuột từ một góc "
                "sang góc đối diện để tạo hình chữ nhật; 4 góc sẽ được điền tự động."
            )
            self.image_view.update()
        except Exception as exc:
            QMessageBox.critical(self, "Không chụp được màn hình", str(exc))

    def _on_image_click(self, x: int, y: int) -> None:
        if self._pixmap.isNull():
            return
        if self.mode_combo.currentData() == "region":
            names = ["top_left", "top_right", "bottom_right", "bottom_left"]
            if len(self._points) >= 4:
                QMessageBox.information(
                    self, "Đã đủ 4 điểm", "Hãy lưu vùng hoặc xóa điểm để chọn lại."
                )
                return
            label = names[len(self._points)]
        else:
            suggested = self.point_name.text().strip() or f"point_{len(self._points) + 1}"
            label, accepted = QInputDialog.getText(
                self, "Đặt tên tọa độ", "Tên điểm (ví dụ guild_check_in):",
                text=suggested,
            )
            if not accepted:
                return
            label = label.strip()
            if not label:
                QMessageBox.warning(self, "Thiếu tên", "Tên điểm không được để trống.")
                return
            self.point_name.setText(label)
        self._points.append((x, y, label))
        self.image_view.set_points(self._points)
        ratio_x = x / self._pixmap.width()
        ratio_y = y / self._pixmap.height()
        self.instruction.setText(
            f"Đã chọn {len(self._points)} điểm — {label}: pixel=({x}, {y}), "
            f"ratio=({ratio_x:.6f}, {ratio_y:.6f})"
        )

    def _on_image_rect_selected(self, left: int, top: int, right: int, bottom: int) -> None:
        """Convert a dragged rectangle into four consistently aligned corners."""
        self._points = [
            (left, top, "top_left"),
            (right, top, "top_right"),
            (right, bottom, "bottom_right"),
            (left, bottom, "bottom_left"),
        ]
        self.image_view.set_points(self._points)
        self.instruction.setText(
            f"Đã chọn hình chữ nhật: trái={left}, trên={top}, phải={right}, dưới={bottom} "
            "— có thể kéo lại để chỉnh hoặc lưu vùng."
        )

    def undo_point(self) -> None:
        if self._points:
            self._points.pop()
            self.image_view.set_points(self._points)
            self.instruction.setText(f"Còn {len(self._points)} điểm đã chọn.")

    def clear_points(self) -> None:
        self._points.clear()
        self.image_view.set_points(self._points)
        self.instruction.setText("Đã xóa lựa chọn. Có thể nhấp chọn điểm hoặc kéo tạo hình chữ nhật.")

    def save_coordinates(self) -> None:
        if self._pixmap.isNull() or self._image_path is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Hãy chụp màn hình trước.")
            return
        if not self._points:
            QMessageBox.warning(self, "Chưa chọn điểm", "Hãy nhấp chọn ít nhất một điểm trên ảnh.")
            return

        width, height = self._pixmap.width(), self._pixmap.height()
        mode = self.mode_combo.currentData()
        try:
            if mode == "point":
                screen = self.screen_name.text().strip()
                if not screen:
                    raise ValueError("Tên màn hình không được để trống.")
                data = self._read_json(LOCATIONS_PATH, {"reference_resolution": [width, height], "screens": {}})
                data.setdefault("reference_resolution", [width, height])
                data.setdefault("screens", {})
                if not isinstance(data["screens"], dict):
                    raise ValueError("Khóa 'screens' trong locations.json không hợp lệ.")
                screen_data = data["screens"].setdefault(screen, {})
                if not isinstance(screen_data, dict):
                    raise ValueError(f"Màn hình {screen!r} trong locations.json không hợp lệ.")
                for x, y, label in self._points:
                    screen_data[label] = {
                        "x": round(x / width, 6),
                        "y": round(y / height, 6),
                        "x_px": x,
                        "y_px": y,
                    }
                LOCATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                LOCATIONS_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                message = f"Đã lưu {len(self._points)} điểm vào {LOCATIONS_PATH}"
            else:
                if len(self._points) != 4:
                    raise ValueError(f"Vùng cần đúng 4 góc; hiện có {len(self._points)} điểm.")
                name = self.region_name.text().strip()
                if not name:
                    raise ValueError("Tên vùng không được để trống.")
                region = {
                    "name": name,
                    "serial": self.serial or "desktop",
                    "screenshot": str(self._image_path),
                    "image_resolution": [width, height],
                    "corners_order": ["top_left", "top_right", "bottom_right", "bottom_left"],
                    "corners": [
                        {
                            "name": label,
                            "x_px": x,
                            "y_px": y,
                            "x_ratio": round(x / width, 6),
                            "y_ratio": round(y / height, 6),
                        }
                        for x, y, label in self._points
                    ],
                    "bounds": {
                        "left": min(p[0] for p in self._points),
                        "top": min(p[1] for p in self._points),
                        "right": max(p[0] for p in self._points),
                        "bottom": max(p[1] for p in self._points),
                    },
                    "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
                data = self._read_json(REGIONS_PATH, {"regions": {}})
                data.setdefault("regions", {})
                if not isinstance(data["regions"], dict):
                    raise ValueError("Khóa 'regions' trong regions.json không hợp lệ.")
                data["regions"][name] = region
                REGIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                REGIONS_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                message = f"Đã lưu vùng {name!r} vào {REGIONS_PATH}"
            QMessageBox.information(self, "Đã lưu tọa độ", message)
            self.instruction.setText(message)
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
