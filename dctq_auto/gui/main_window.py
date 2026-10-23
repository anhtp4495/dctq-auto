"""Main PySide6 window with task tabs and shared controls."""

import logging
import time

from PySide6.QtCore import Qt, QTimer, QSettings, QThread, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.adb.client import AdbClient
from dctq_auto.config.settings import Settings
from dctq_auto.gui.clone_tab import CloneTab
from dctq_auto.gui.screenshot_annotator import ScreenshotAnnotator
from dctq_auto.tasks.clone.accounts import load_accounts


SCREENSHOT_DIR = "artifacts/screenshots"


class ScreenshotCaptureWorker(QThread):
    """Capture an ADB screenshot or save a desktop image without blocking the UI."""

    saved = Signal(str)
    failed = Signal(str)

    def __init__(self, path: str, serial: str | None = None, desktop_image=None, parent=None):
        super().__init__(parent)
        self.path = path
        self.serial = serial
        self.desktop_image = desktop_image

    def run(self) -> None:
        try:
            from pathlib import Path
            target = Path(self.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if self.serial is not None:
                image = AdbClient(self.serial).connect().screenshot()
                image.save(str(target))
            else:
                if self.desktop_image is None or not self.desktop_image.save(str(target), "PNG"):
                    raise RuntimeError("Không lưu được ảnh chụp desktop.")
            self.saved.emit(str(target))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DCTQ Auto")
        self.setStyleSheet("QGroupBox { border: 0; margin-top: 8px; padding-top: 4px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0; }")
        self._ui_settings = QSettings("DCTQAuto", "DCTQAuto")
        self._settings = Settings.from_env()
        self._worker = None
        self._paused = False
        self._run_started_at: float | None = None
        self._pause_started_at: float | None = None
        self._active_clone_mode = False
        self._active_mock_mode = False
        self._clone_total_accounts = 0
        self._paused_duration = 0.0
        self._screenshot_worker = None
        self._screenshot_annotator = None
        self._analysis_lock_states: dict[QWidget, bool] = {}
        self._settings_lock_states: dict[QWidget, bool] = {}
        self.last_screen_short: str | None = None

        central = QWidget(self)
        root = QVBoxLayout(central)

        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        top_row = QVBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        device_panel = QGroupBox("Quét thiết bị")
        device_layout = QVBoxLayout(device_panel)
        device_layout.setContentsMargins(8, 8, 8, 8)
        self.scan_button = QPushButton("Quét thiết bị")
        self.scan_button.clicked.connect(self.scan_adb_devices)
        device_layout.addWidget(self.scan_button)

        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(66)
        self.device_list.setMaximumHeight(72)
        self.device_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.device_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        device_layout.addWidget(self.device_list)
        # Keep the device list compact; don't let it stretch and create a gap above the buttons.
        top_row.addWidget(device_panel, 0)

        # Keep the combo as the settings-compatible source of the selected serial.
        # The visible QListWidget provides a compact, scrollable device list.
        self.device_combo = QComboBox(self)
        self.device_combo.hide()
        self.device_combo.addItem("Mock-Adb", "mock")
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.device_list.currentItemChanged.connect(self._on_device_list_selection_changed)
        self._sync_device_list_from_combo()
        controls_panel = QWidget()
        capture_row = QHBoxLayout(controls_panel)
        capture_row.setContentsMargins(8, 0, 8, 8)
        capture_row.setSpacing(5)
        # Keep the control icons anchored to the right edge as the window resizes.
        capture_row.addStretch(1)
        self.start_button = QPushButton("▶")
        self.start_button.setFixedSize(38, 30)
        self.start_button.setToolTip("Bắt đầu")
        self.start_button.clicked.connect(self.start_bot)
        capture_row.addWidget(self.start_button)

        self.pause_button = QPushButton("⏸")
        self.pause_button.setFixedSize(38, 30)
        self.pause_button.setToolTip("Tạm dừng")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause_bot)
        self.pause_button.setToolTip("Tạm dừng")
        capture_row.addWidget(self.pause_button)

        self.stop_button = QPushButton("⏹")
        self.stop_button.setFixedSize(38, 30)
        self.stop_button.setToolTip("Dừng hẳn")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_bot)
        capture_row.addWidget(self.stop_button)

        # Use the same native button appearance as the screenshot/analyze controls.
        # Qt handles the disabled appearance automatically.

        self.capture_annotate_button = QPushButton("📷")
        self.capture_annotate_button.setFixedSize(38, 30)
        self.capture_annotate_button.setToolTip(
            "Chụp màn hình và lưu một ảnh vào artifacts/screenshots."
        )
        self.capture_annotate_button.clicked.connect(self.capture_screenshot_to_file)
        capture_row.addWidget(self.capture_annotate_button)
        self.choose_position_button = QPushButton("🔍")
        self.choose_position_button.setFixedSize(38, 30)
        self.choose_position_button.setToolTip(
            "Phân tích ảnh chụp và chọn tọa độ (Analyze)."
        )
        self.choose_position_button.clicked.connect(self.open_screenshot_annotator)
        capture_row.addWidget(self.choose_position_button)
        top_row.addWidget(controls_panel, 0)
        root.addLayout(top_row)
        root.setSpacing(0)

        self.tabs = QTabWidget(central)
        root.addWidget(self.tabs, 1)

        self.giao_tranh = QSpinBox()
        self.giao_tranh.setRange(1, 60)
        self.giao_tranh.setValue(15)
        self.giao_tranh.setKeyboardTracking(False)
        self.giao_tranh.editingFinished.connect(self.giao_tranh.clearFocus)

        self.tranh_ba = QSpinBox()
        self.tranh_ba.setRange(1, 15)
        self.tranh_ba.setValue(6)
        self.tranh_ba.setKeyboardTracking(False)
        self.tranh_ba.editingFinished.connect(self.tranh_ba.clearFocus)

        self.chon_nha_npc = QCheckBox("Chọn nhà NPC")
        self.giao_tranh_nhanh_1_co = QCheckBox("Nhanh 1 cờ")
        self.ba_co = QCheckBox("Bình thường 3 cờ")
        self.thoi_gian_mode = QCheckBox("Thời gian tối đa:")
        self.giao_tranh_nhanh_1_co.setToolTip("Chỉ cần thắng trận là kết thúc.")
        self.giao_tranh_nhanh_1_co.setChecked(False)
        self.ba_co.setChecked(True)
        self.giao_tranh_mode_group = QButtonGroup(self)
        self.giao_tranh_mode_group.setExclusive(True)
        self.giao_tranh_mode_group.addButton(self.giao_tranh_nhanh_1_co)
        self.giao_tranh_mode_group.addButton(self.ba_co)
        self.giao_tranh_mode_group.addButton(self.thoi_gian_mode)
        self.su_dung_canh_bat_tran = QCheckBox("Sử dụng Canh Bát Trân")
        self.thoi_gian_giao_tranh = QSpinBox()
        self.thoi_gian_giao_tranh.setRange(15, 180)
        self.thoi_gian_giao_tranh.setValue(15)
        self.thoi_gian_giao_tranh.setSuffix(" giây")
        self.thoi_gian_giao_tranh.setKeyboardTracking(False)
        self.thoi_gian_giao_tranh.editingFinished.connect(
            self.thoi_gian_giao_tranh.clearFocus
        )
        self.thoi_gian_giao_tranh.setEnabled(False)
        self.thoi_gian_mode.toggled.connect(
            self.thoi_gian_giao_tranh.setEnabled
        )
        self.giao_tranh_nhanh_1_co.toggled.connect(
            self._update_giao_tranh_mode_description
        )
        self.ba_co.toggled.connect(self._update_giao_tranh_mode_description)
        self.thoi_gian_mode.toggled.connect(
            self._update_giao_tranh_mode_description
        )
        self.giao_tranh_mode_description = QLabel()
        self.giao_tranh_mode_description.setWordWrap(True)
        self._update_giao_tranh_mode_description()
        self.ha_chien_cong = QCheckBox("Hạ chiến công")
        self.chien_cong = QSpinBox()
        self.chien_cong.setRange(200, 4000)
        self.chien_cong.setValue(200)
        self.chien_cong.setKeyboardTracking(False)
        self.chien_cong.editingFinished.connect(self.chien_cong.clearFocus)

        self.giao_tranh_options = QWidget()
        options_layout = QGridLayout(self.giao_tranh_options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setHorizontalSpacing(16)
        options_layout.setVerticalSpacing(4)
        options_layout.addWidget(self.chon_nha_npc, 0, 0)
        options_layout.addWidget(self.su_dung_canh_bat_tran, 0, 1)
        giao_tranh_mode_row = self._build_mode_row(
            self.giao_tranh_nhanh_1_co,
            self.ba_co,
            self.thoi_gian_mode,
            self.thoi_gian_giao_tranh,
        )
        options_layout.addWidget(giao_tranh_mode_row, 1, 0, 1, 5)
        options_layout.addWidget(self.giao_tranh_mode_description, 2, 0, 1, 5)

        self.chien_cong_row = QWidget()
        chien_cong_layout = QHBoxLayout(self.chien_cong_row)
        chien_cong_layout.setContentsMargins(0, 0, 0, 0)
        chien_cong_layout.addWidget(QLabel("Chiến công cần hạ:"))
        chien_cong_layout.addWidget(self.chien_cong)
        chien_cong_layout.addStretch(1)
        self.chien_cong.setEnabled(False)
        self.ha_chien_cong.toggled.connect(self._toggle_chien_cong_mode)

        self.mua_luot_knb = QCheckBox("Mua lượt bằng KNB")
        self.mua_luot_knb.setChecked(False)
        self.tranh_ba_1_co = QCheckBox("Nhanh 1 cờ")
        self.tranh_ba_1_co.setToolTip("Chỉ cần thắng trận là kết thúc.")
        self.tranh_ba_4_co = QCheckBox("Bình thường 4 cờ")
        self.tranh_ba_4_co.setMinimumWidth(self.ba_co.sizeHint().width())
        self.tranh_ba_thoi_gian_mode = QCheckBox("Thời gian tối đa:")
        self.tranh_ba_mode_group = QButtonGroup(self)
        self.tranh_ba_mode_group.setExclusive(True)
        self.tranh_ba_mode_group.addButton(self.tranh_ba_1_co)
        self.tranh_ba_mode_group.addButton(self.tranh_ba_4_co)
        self.tranh_ba_mode_group.addButton(self.tranh_ba_thoi_gian_mode)
        self.tranh_ba_thoi_gian = QSpinBox()
        self.tranh_ba_thoi_gian.setRange(15, 180)
        self.tranh_ba_thoi_gian.setValue(15)
        self.tranh_ba_thoi_gian.setSuffix(" giây")
        self.tranh_ba_thoi_gian.setKeyboardTracking(False)
        self.tranh_ba_thoi_gian.editingFinished.connect(
            self.tranh_ba_thoi_gian.clearFocus
        )
        self.tranh_ba_thoi_gian.setEnabled(False)
        self.tranh_ba_thoi_gian_mode.toggled.connect(
            self.tranh_ba_thoi_gian.setEnabled
        )
        self.tranh_ba_thoi_gian_mode.setToolTip(
            "Kết thúc trận khi đạt giới hạn thời gian đã chọn."
        )
        self.tranh_ba_1_co.toggled.connect(
            self._update_tranh_ba_mode_description
        )
        self.tranh_ba_4_co.toggled.connect(
            self._update_tranh_ba_mode_description
        )
        self.tranh_ba_thoi_gian_mode.toggled.connect(
            self._update_tranh_ba_mode_description
        )
        self.tranh_ba_mode_description = QLabel()
        self.tranh_ba_mode_description.setWordWrap(True)
        self.tranh_ba_4_co.setChecked(True)
        self._update_tranh_ba_mode_description()

        self.diem_danh = QCheckBox("Điểm danh hằng ngày")
        self.diem_danh.setChecked(True)
        self.bao_danh_quan_doan = QCheckBox("Báo danh quân đoàn")
        self.bao_danh_quan_doan.setChecked(True)

        self.dong_gop_knb = QCheckBox("Đóng góp KNB")
        self.so_lan_dong_gop_knb = QSpinBox()
        self.so_lan_dong_gop_knb.setRange(1, 10)
        self.so_lan_dong_gop_knb.setValue(1)
        self.so_lan_dong_gop_knb.setEnabled(False)
        self.so_lan_dong_gop_knb.setKeyboardTracking(False)
        self.dong_gop_knb.toggled.connect(self.so_lan_dong_gop_knb.setEnabled)

        self.tham_do_lanh_dia = QCheckBox("Thăm dò lãnh địa")
        self.so_lan_tham_do_lanh_dia = QSpinBox()
        self.so_lan_tham_do_lanh_dia.setRange(1, 10)
        self.so_lan_tham_do_lanh_dia.setValue(1)
        self.so_lan_tham_do_lanh_dia.setEnabled(False)
        self.so_lan_tham_do_lanh_dia.setKeyboardTracking(False)
        self.tham_do_lanh_dia.toggled.connect(
            self.so_lan_tham_do_lanh_dia.setEnabled
        )
        self.tham_do_lanh_dia_knb = QCheckBox("Mua lượt thiếu bằng KNB")
        self.tham_do_lanh_dia_knb.setEnabled(False)
        self.tham_do_lanh_dia.toggled.connect(
            self.tham_do_lanh_dia_knb.setEnabled
        )
        self.tham_do_lanh_dia_description = QLabel()
        self.tham_do_lanh_dia_description.setWordWrap(True)
        self.tham_do_lanh_dia_knb.toggled.connect(
            self._update_tham_do_lanh_dia_description
        )
        self._update_tham_do_lanh_dia_description()

        self.nhiem_vu_luu_ly_thap = QCheckBox("Nhiệm vụ Lưu Ly Tháp")
        self.so_lan_luu_ly_thap = QSpinBox()
        self.so_lan_luu_ly_thap.setRange(6, 10)
        self.so_lan_luu_ly_thap.setValue(6)
        self.so_lan_luu_ly_thap.setEnabled(False)
        self.so_lan_luu_ly_thap.setKeyboardTracking(False)
        self.nhiem_vu_luu_ly_thap.toggled.connect(
            self.so_lan_luu_ly_thap.setEnabled
        )
        self.luu_ly_thap_knb = QCheckBox("Mua lượt thiếu bằng KNB")
        self.luu_ly_thap_knb.setEnabled(False)
        self.nhiem_vu_luu_ly_thap.toggled.connect(
            self.luu_ly_thap_knb.setEnabled
        )
        self.luu_ly_thap_description = QLabel()
        self.luu_ly_thap_description.setWordWrap(True)
        self.luu_ly_thap_knb.toggled.connect(
            self._update_luu_ly_thap_description
        )
        self._update_luu_ly_thap_description()
        self.thiet_lap_muu_binh = QCheckBox("Thiết lập phòng thủ")
        self.thiet_lap_muu_binh.setChecked(True)
        self.vuot_ai_muu_binh = QCheckBox("Vượt Ải")

        self.tabs.addTab(self._build_daily_tab(), "Nhiệm vụ hằng ngày")
        self.tabs.addTab(self._build_strategy_tab(), "Mưu Binh")
        self.tabs.addTab(self._build_war_tab(), "Quốc chiến")
        self.clone_tab = CloneTab()
        self.tabs.addTab(self.clone_tab, "Clone")
        self.thoat_quan_doan_task = QCheckBox("Thoát màn hình Quân đoàn")
        self.thoat_quan_doan_task.setToolTip(
            "Đóng giao diện Quân đoàn đang mở, không rời khỏi bang hội."
        )
        self.doi_tai_khoan_task = QCheckBox("Đổi tài khoản")
        self.doi_tai_khoan_task.setToolTip(
            "Mở hồ sơ → Tùy chọn → Cài đặt người dùng → Đổi tài khoản; "
            "chỉ xác nhận khi nhận diện đúng hộp thoại."
        )
        self.tabs.addTab(self._build_tasks_tab(), "Tác vụ")

        progress_group = QGroupBox("Tiến trình")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)
        self.current_activity_label = QLabel("Đang xử lý: Chưa chạy")
        self.current_activity_label.setWordWrap(True)
        progress_layout.addWidget(self.current_activity_label)
        self.clone_result_list = QListWidget()
        self.clone_result_list.setObjectName("cloneAccountResults")
        self.clone_result_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.clone_result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.clone_result_list.setUniformItemSizes(True)
        self.clone_result_list.setFixedHeight(5 * 24 + 4)
        self.clone_result_list.hide()
        progress_layout.addWidget(self.clone_result_list)
        self.task_progress_list = QListWidget()
        self.task_progress_list.setObjectName("taskProgressList")
        self.task_progress_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.task_progress_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_progress_list.setUniformItemSizes(True)
        self.task_progress_list.setFixedHeight(5 * 24 + 4)
        progress_layout.addWidget(self.task_progress_list)
        self.task_progress_labels: dict[str, QListWidgetItem] = {}
        timing_layout = QHBoxLayout()
        self.elapsed_time_label = QLabel("Thời gian đã chạy: 00:00:00")
        self.eta_label = QLabel("Dự kiến kết thúc: Chưa ước tính")
        timing_layout.addWidget(self.elapsed_time_label)
        timing_layout.addStretch(1)
        timing_layout.addWidget(self.eta_label)
        progress_layout.addLayout(timing_layout)
        root.addWidget(progress_group, 0)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)

        self.setCentralWidget(central)
        self._restore_settings()
        # Sync dependent controls after persisted checkbox states are restored.
        self._toggle_task_battle_options(self.task_battle.isChecked())
        self._place_window_on_right()
        # Restore saved geometry after the native Windows frame has been created.
        # Restoring before show() can shift the outer frame vertically by the
        # title-bar height on some DPI settings.
        QTimer.singleShot(0, self._restore_window_geometry_after_show)
        self._connect_settings_persistence()
        self.tabs.currentChanged.connect(self._save_settings)
        self.clone_tab.account_file_combo.currentIndexChanged.connect(self._save_settings)
        self._on_device_changed()
        self._log(
            "Ứng dụng đã khởi động. Chọn Chạy thử hoặc một thiết bị ADB."
        )


    def _place_window_on_right(self) -> None:
        """Use a safe initial placement; saved geometry is restored after show()."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(333, 760)
            return

        area = screen.availableGeometry()
        width = min(333, area.width())
        self.setMinimumWidth(min(300, width))

        saved_geometry = self._ui_settings.value("ui/window_geometry")
        if saved_geometry:
            # Defer restoreGeometry until the native window frame exists.
            self._has_saved_window_geometry = True
            self.resize(width, max(1, area.height() - 48))
            self.move(area.right() - width + 1, area.top())
            return

        self._has_saved_window_geometry = False
        # QWidget.resize() sets the client size; the native frame adds height.
        height = max(1, area.height() - 48)
        self.resize(width, height)
        self.move(area.right() - width + 1, area.top())

    def _restore_window_geometry_after_show(self) -> None:
        """Restore saved geometry once Windows has initialized the native frame."""
        if not getattr(self, "_has_saved_window_geometry", False):
            return

        saved_geometry = self._ui_settings.value("ui/window_geometry")
        if not saved_geometry or not self.restoreGeometry(saved_geometry):
            return

        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()
        frame = self.frameGeometry()
        if frame.width() > area.width() or frame.height() > area.height():
            self.resize(
                min(self.width(), area.width()),
                max(1, min(self.height(), area.height() - 30)),
            )
            frame = self.frameGeometry()

        # Clamp the outer frame, not the client rectangle, to avoid title-bar
        # offsets causing the window to drift on each launch.
        x = min(max(frame.x(), area.left()), area.right() - frame.width() + 1)
        y = min(max(frame.y(), area.top()), area.bottom() - frame.height() + 1)
        self.move(x, y)

    def _print_window_geometry(self) -> None:
        """Print actual window and screen geometry to the console for layout debugging."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else None
        frame = self.frameGeometry()
        client = self.geometry()
        details = (
            "\n[DCTQ Auto window geometry]"
            f"\n  screen: {screen.name() if screen is not None else 'None'}"
            f"\n  availableGeometry: {area.getRect() if area is not None else 'None'}"
            f"\n  geometry (client): {client.getRect()}"
            f"\n  frameGeometry (outer): {frame.getRect()}"
            f"\n  pos: ({self.x()}, {self.y()})"
            f"\n  size: ({self.width()}, {self.height()})"
            f"\n  frameSize: ({frame.width()}, {frame.height()})"
            f"\n  devicePixelRatio: {screen.devicePixelRatio() if screen is not None else 'None'}"
            f"\n  visible: {self.isVisible()}"
            f"\n  windowState: {self.windowState()}"
        )
        print(details, flush=True)

    def _settings_widgets(self) -> dict[str, QWidget]:
        """Return named controls whose values should persist between launches."""
        supported = (QCheckBox, QRadioButton, QSpinBox, QComboBox, QGroupBox)
        widgets: dict[str, QWidget] = {}
        for name, widget in self.__dict__.items():
            if not isinstance(widget, supported):
                continue
            if isinstance(widget, QGroupBox) and not widget.isCheckable():
                continue
            if name in {"device_combo"}:
                continue
            widgets[name] = widget
        return widgets

    def _restore_settings(self) -> None:
        for name, widget in self._settings_widgets().items():
            key = f"controls/{name}"
            if not self._ui_settings.contains(key):
                continue
            value = self._ui_settings.value(key)
            if isinstance(widget, (QCheckBox, QRadioButton, QGroupBox)):
                widget.setChecked(str(value).lower() in {"true", "1", "yes"})
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(value))
                except (TypeError, ValueError):
                    pass
            elif isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index < 0:
                    index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)

        tab_index = self._ui_settings.value("ui/selected_tab", 0)
        try:
            tab_index = int(tab_index)
        except (TypeError, ValueError):
            tab_index = 0
        if hasattr(self, "tabs") and self.tabs.count():
            self.tabs.setCurrentIndex(max(0, min(tab_index, self.tabs.count() - 1)))

        if hasattr(self, "clone_tab"):
            account_files = self._ui_settings.value("clone/account_files", [])
            if isinstance(account_files, str):
                account_files = [account_files] if account_files else []
            account_file = self._ui_settings.value("clone/account_file", "")
            self.clone_tab.set_account_files(list(account_files or []), str(account_file or ""))
            for name, widget in self._clone_settings_widgets().items():
                key = f"clone/controls/{name}"
                if self._ui_settings.contains(key):
                    value = self._ui_settings.value(key)
                    widget.setChecked(str(value).lower() in {"true", "1", "yes"})

    def _clone_settings_widgets(self) -> dict[str, QCheckBox]:
        """Return Clone tab task toggles that must survive app restarts."""
        if not hasattr(self, "clone_tab"):
            return {}
        return {
            name: getattr(self.clone_tab, name)
            for name in (
                "clone_daily_check_in",
                "clone_receive_quoc_van",
                "clone_guild_check_in",
                "clone_receive_lucky_bag",
                "clone_guild_fortune",
                "clone_quoc_chien",
            )
        }

    def _connect_settings_persistence(self) -> None:
        for widget in self._settings_widgets().values():
            if isinstance(widget, (QCheckBox, QRadioButton, QGroupBox)):
                widget.toggled.connect(self._save_settings)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._save_settings)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._save_settings)
        for widget in self._clone_settings_widgets().values():
            widget.toggled.connect(self._save_settings)

    def _save_settings(self, *_args) -> None:
        for name, widget in self._settings_widgets().items():
            if isinstance(widget, (QCheckBox, QRadioButton, QGroupBox)):
                value = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentData()
                if value is None:
                    value = widget.currentText()
            else:
                continue
            self._ui_settings.setValue(f"controls/{name}", value)
        if hasattr(self, "tabs"):
            self._ui_settings.setValue("ui/selected_tab", self.tabs.currentIndex())
        if hasattr(self, "clone_tab"):
            self._ui_settings.setValue(
                "clone/account_file", self.clone_tab.account_file()
            )
            self._ui_settings.setValue(
                "clone/account_files", self.clone_tab.account_files()
            )
            for name, widget in self._clone_settings_widgets().items():
                self._ui_settings.setValue(f"clone/controls/{name}", widget.isChecked())
        self._ui_settings.sync()

    def closeEvent(self, event) -> None:
        self._ui_settings.setValue("ui/window_geometry", self.saveGeometry())
        self._ui_settings.sync()
        self._save_settings()
        super().closeEvent(event)

    def _build_mode_row(self, *widgets: QWidget) -> QWidget:
        """Build mode options with the same first-column width and spacing."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(16)

        label = QLabel("Chế độ:")
        label.setFixedWidth(self.chon_nha_npc.sizeHint().width())
        row_layout.addWidget(label)
        for widget in widgets:
            row_layout.addWidget(widget)

        row_layout.addStretch(1)
        return row

    def _build_daily_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        giao_tranh_group = QGroupBox("Giao tranh")
        giao_tranh_group.setCheckable(True)
        giao_tranh_group.setChecked(True)
        self.giao_tranh_group = giao_tranh_group
        giao_tranh_layout = QVBoxLayout(giao_tranh_group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số trận:"))
        row.addStretch(1)
        self.giao_tranh.setMinimumWidth(120)
        row.addWidget(self.giao_tranh)
        giao_tranh_layout.addLayout(row)
        ha_chien_cong_row = QHBoxLayout()
        ha_chien_cong_row.addWidget(self.ha_chien_cong)
        ha_chien_cong_row.addWidget(self.chien_cong_row)
        ha_chien_cong_row.addStretch(1)
        giao_tranh_layout.addLayout(ha_chien_cong_row)
        giao_tranh_layout.addWidget(self.giao_tranh_options)
        layout.addWidget(giao_tranh_group)

        tranh_ba_group = QGroupBox("Tranh bá")
        tranh_ba_group.setCheckable(True)
        tranh_ba_group.setChecked(True)
        self.tranh_ba_group = tranh_ba_group
        tranh_ba_layout = QVBoxLayout(tranh_ba_group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số trận:"))
        row.addStretch(1)
        self.tranh_ba.setMinimumWidth(120)
        row.addWidget(self.tranh_ba)
        tranh_ba_layout.addLayout(row)
        tranh_ba_layout.addWidget(self.mua_luot_knb)
        tranh_ba_mode_row = self._build_mode_row(
            self.tranh_ba_1_co,
            self.tranh_ba_4_co,
            self.tranh_ba_thoi_gian_mode,
            self.tranh_ba_thoi_gian,
        )
        tranh_ba_layout.addWidget(tranh_ba_mode_row)
        tranh_ba_layout.addWidget(self.tranh_ba_mode_description)
        layout.addWidget(tranh_ba_group)

        other_group = QGroupBox("Nhiệm vụ khác")
        other_layout = QGridLayout(other_group)
        other_layout.addWidget(self.diem_danh, 0, 0)
        other_layout.addWidget(self.bao_danh_quan_doan, 0, 1)
        other_layout.addWidget(self.dong_gop_knb, 1, 0)
        other_layout.addWidget(self.so_lan_dong_gop_knb, 1, 1)
        other_layout.addWidget(QLabel("lần"), 1, 2)
        other_layout.addWidget(self.tham_do_lanh_dia, 2, 0)
        other_layout.addWidget(self.so_lan_tham_do_lanh_dia, 2, 1)
        other_layout.addWidget(QLabel("lần"), 2, 2)
        other_layout.addWidget(self.tham_do_lanh_dia_knb, 2, 3)
        other_layout.addWidget(self.tham_do_lanh_dia_description, 3, 0, 1, 4)
        other_layout.addWidget(self.nhiem_vu_luu_ly_thap, 4, 0)
        other_layout.addWidget(self.so_lan_luu_ly_thap, 4, 1)
        other_layout.addWidget(QLabel("lần"), 4, 2)
        other_layout.addWidget(self.luu_ly_thap_knb, 4, 3)
        other_layout.addWidget(self.luu_ly_thap_description, 5, 0, 1, 4)
        layout.addWidget(other_group)

        layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(page)
        return scroll_area

    def _update_giao_tranh_mode_description(self, *_args) -> None:
        if self.thoi_gian_mode.isChecked():
            self.giao_tranh_mode_description.setText(
                "Kết thúc trận khi đạt giới hạn thời gian đã chọn, dù đã thắng hay chưa."
            )
        elif self.giao_tranh_nhanh_1_co.isChecked():
            self.giao_tranh_mode_description.setText(
                "Chỉ cần thắng trận là kết thúc, không cần đủ 3 cờ."
            )
        else:
            self.giao_tranh_mode_description.setText(
                "Đánh đến khi chắc chắn thắng và đạt đủ 3 cờ mới kết thúc."
            )

    def _update_tham_do_lanh_dia_description(self, *_args) -> None:
        if self.tham_do_lanh_dia_knb.isChecked():
            self.tham_do_lanh_dia_description.setText(
                "Nếu không đủ phiếu thăm dò, tự động mua các lượt còn thiếu bằng KNB."
            )
        else:
            self.tham_do_lanh_dia_description.setText(
                "Chỉ sử dụng phiếu thăm dò miễn phí, không mua thêm lượt bằng KNB."
            )

    def _update_luu_ly_thap_description(self, *_args) -> None:
        if self.luu_ly_thap_knb.isChecked():
            self.luu_ly_thap_description.setText(
                "Nếu không đủ lượt miễn phí, tự động mua các lượt còn thiếu bằng KNB."
            )
        else:
            self.luu_ly_thap_description.setText(
                "Chỉ sử dụng lượt miễn phí, không mua thêm lượt bằng KNB."
            )

    def _update_tranh_ba_mode_description(self, *_args) -> None:
        if self.tranh_ba_thoi_gian_mode.isChecked():
            self.tranh_ba_mode_description.setText(
                "Kết thúc trận khi đạt giới hạn thời gian đã chọn, dù đã thắng hay chưa."
            )
        elif self.tranh_ba_1_co.isChecked():
            self.tranh_ba_mode_description.setText(
                "Chỉ cần thắng trận là kết thúc, không cần đủ 4 cờ."
            )
        else:
            self.tranh_ba_mode_description.setText(
                "Đánh đến khi chắc chắn thắng và đạt đủ 4 cờ mới kết thúc."
            )

    def _update_task_battle_mode_description(self, *_args) -> None:
        if self.task_battle_time_mode.isChecked():
            self.task_battle_mode_description.setText(
                "Kết thúc trận khi đạt giới hạn thời gian đã chọn, dù đã thắng hay chưa."
            )
        elif self.task_battle_fast_one_flag.isChecked():
            self.task_battle_mode_description.setText(
                "Chỉ cần thắng trận là kết thúc, không cần đủ 3 cờ."
            )
        else:
            self.task_battle_mode_description.setText(
                "Đánh đến khi chắc chắn thắng và đạt đủ 3 cờ mới kết thúc."
            )

    def _toggle_task_battle_options(self, enabled: bool) -> None:
        self.task_battle_lower_merit.setEnabled(enabled)
        self.task_battle_merit_target.setEnabled(
            enabled and self.task_battle_lower_merit.isChecked()
        )
        self._toggle_task_battle_merit_mode(
            self.task_battle_lower_merit.isChecked()
        )

    def _toggle_task_battle_merit_mode(self, lower_merit: bool) -> None:
        battle_enabled = self.task_battle.isChecked()
        for widget in (
            self.task_battle_npc_house,
            self.task_battle_use_bazhen,
            self.task_battle_fast_one_flag,
            self.task_battle_three_flags,
            self.task_battle_time_mode,
        ):
            widget.setEnabled(battle_enabled and not lower_merit)
        self.task_battle_time_limit.setEnabled(
            battle_enabled
            and not lower_merit
            and self.task_battle_time_mode.isChecked()
        )

    def _toggle_task_championship_options(self, enabled: bool) -> None:
        self.task_championship_knb.setEnabled(enabled)
        self.task_championship_fast_one_flag.setEnabled(enabled)
        self.task_championship_four_flags.setEnabled(enabled)
        self.task_championship_time_mode.setEnabled(enabled)
        self.task_championship_time_limit.setEnabled(
            enabled and self.task_championship_time_mode.isChecked()
        )

    def _update_task_championship_mode_description(self, *_args) -> None:
        if self.task_championship_time_mode.isChecked():
            self.task_championship_mode_description.setText(
                "Kết thúc trận khi đạt giới hạn thời gian đã chọn, dù đã thắng hay chưa."
            )
        elif self.task_championship_fast_one_flag.isChecked():
            self.task_championship_mode_description.setText(
                "Chỉ cần thắng trận là kết thúc, không cần đủ 4 cờ."
            )
        else:
            self.task_championship_mode_description.setText(
                "Đánh đến khi chắc chắn thắng và đạt đủ 4 cờ mới kết thúc."
            )

    def _toggle_chien_cong_mode(self, enabled: bool) -> None:
        self.chon_nha_npc.setEnabled(not enabled)
        self.giao_tranh_nhanh_1_co.setEnabled(not enabled)
        self.ba_co.setEnabled(not enabled)
        self.thoi_gian_mode.setEnabled(not enabled)
        self.thoi_gian_giao_tranh.setEnabled(
            not enabled and self.thoi_gian_mode.isChecked()
        )
        self.su_dung_canh_bat_tran.setEnabled(not enabled)
        self.chien_cong.setEnabled(enabled)

    @staticmethod
    def _make_scrollable_tab(page: QWidget) -> QScrollArea:
        """Keep feature tabs aligned and scrollable like the daily-task tab."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(page)
        return scroll_area

    def _build_strategy_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        group = QGroupBox("Tác vụ trong màn hình Mưu Binh")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(self.thiet_lap_muu_binh)
        group_layout.addWidget(self.vuot_ai_muu_binh)
        note = QLabel(
            "Khi chạy tab này: vào màn hình Mưu Binh, thực hiện các chức năng "
            "được chọn, sau đó thoát màn hình."
        )
        note.setWordWrap(True)
        group_layout.addWidget(note)
        layout.addWidget(group)
        layout.addStretch(1)
        return self._make_scrollable_tab(page)

    def _build_war_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        group = QGroupBox("Quốc chiến")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(QLabel("Sẽ bổ sung cấu hình sau."))
        layout.addWidget(group)
        layout.addStretch(1)
        return self._make_scrollable_tab(page)

    def _on_device_changed(self, *_args) -> None:
        mock_mode = self.device_combo.currentData() == "mock"
        self.scan_button.setEnabled(True)
        if mock_mode:
            self._log("Đã chọn chế độ chạy thử, không kết nối ADB.")
        elif self.device_combo.currentData():
            self._log(f"Đã chọn thiết bị ADB: {self.device_combo.currentData()}")

    def capture_screenshot_to_file(self) -> None:
        """Save one screenshot per click and disable the camera icon until saving ends."""
        if self._screenshot_worker is not None and self._screenshot_worker.isRunning():
            return
        from datetime import datetime
        from pathlib import Path

        serial = self.device_combo.currentData()
        serial = None if serial == "mock" else str(serial)
        desktop_image = None
        if serial is None:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                QMessageBox.warning(self, "Không chụp được ảnh", "Không tìm thấy màn hình desktop.")
                return
            desktop_image = screen.grabWindow(0).toImage()
        Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = str(Path(SCREENSHOT_DIR) / f"screenshot_{timestamp}.png")

        self.capture_annotate_button.setEnabled(False)
        self.capture_annotate_button.setToolTip("Đang lưu ảnh chụp…")
        self._log("Đang chụp và lưu ảnh màn hình…")
        worker = ScreenshotCaptureWorker(path, serial, desktop_image, self)
        self._screenshot_worker = worker
        worker.saved.connect(self._on_screenshot_saved)
        worker.failed.connect(self._on_screenshot_failed)
        worker.finished.connect(self._on_screenshot_worker_finished)
        worker.start()

    def _on_screenshot_saved(self, path: str) -> None:
        self.last_screen_short = path
        self._log(f"Đã lưu ảnh màn hình: {path}")

    def _on_screenshot_failed(self, error: str) -> None:
        self._log(f"Lỗi chụp/lưu ảnh màn hình: {error}")
        QMessageBox.warning(self, "Không lưu được ảnh", error)

    def _on_screenshot_worker_finished(self) -> None:
        self.capture_annotate_button.setEnabled(True)
        self.capture_annotate_button.setToolTip(
            "Chụp màn hình và lưu một ảnh vào artifacts/screenshots."
        )
        self._screenshot_worker = None

    def open_screenshot_annotator(self) -> None:
        from pathlib import Path

        SCREENSHOT_DIR_PATH = Path(SCREENSHOT_DIR)
        SCREENSHOT_DIR_PATH.mkdir(parents=True, exist_ok=True)
        latest = None
        if self.last_screen_short and Path(self.last_screen_short).is_file():
            latest = Path(self.last_screen_short)
        else:
            candidates = [
                path for path in SCREENSHOT_DIR_PATH.iterdir()
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
            ]
            if candidates:
                latest = max(candidates, key=lambda path: path.stat().st_mtime)
                self.last_screen_short = str(latest)

        serial = self.device_combo.currentData()
        self._open_screenshot_annotator(
            None if serial == "mock" else str(serial),
            initial_image=latest,
        )

    def _open_screenshot_annotator(self, serial: str | None, initial_image=None) -> None:
        # Reuse the existing analysis window instead of opening duplicates.
        if self._screenshot_annotator is not None:
            try:
                if self._screenshot_annotator.isVisible():
                    self._screenshot_annotator.raise_()
                    self._screenshot_annotator.activateWindow()
                    return
            except RuntimeError:
                # Qt object was already destroyed.
                self._screenshot_annotator = None

        dialog = ScreenshotAnnotator(
            serial, self,
            on_ocr_result=self._log_ocr_results,
            on_location_result=self._log_coordinate_result,
            initial_image=initial_image,
        )
        dialog.setModal(False)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.finished.connect(self._clear_screenshot_annotator_reference)
        dialog.destroyed.connect(self._clear_screenshot_annotator_reference)
        self._screenshot_annotator = dialog
        self._set_analysis_window_lock(True)
        dialog.show()

    def _set_analysis_window_lock(self, locked: bool) -> None:
        """Disable the main UI while the screenshot analyzer is open, except the activity log."""
        if locked:
            if self._analysis_lock_states:
                return
            central = self.centralWidget()
            if central is None:
                return
            widgets_to_lock = list(central.findChildren(QWidget))

            # Snapshot every widget's enabled state before disabling any parent.
            # QWidget.isEnabled() reports effective state, so recording it while
            # ancestors are already disabled would incorrectly save children as disabled.
            self._analysis_lock_states = {
                widget: widget.isEnabled() for widget in widgets_to_lock
            }
            for widget in widgets_to_lock:
                widget.setEnabled(False)
            return

        for widget, was_enabled in list(self._analysis_lock_states.items()):
            try:
                widget.setEnabled(was_enabled)
            except RuntimeError:
                pass
        self._analysis_lock_states.clear()

    def _clear_screenshot_annotator_reference(self, *_args) -> None:
        self._set_analysis_window_lock(False)
        self._screenshot_annotator = None

    def _log_coordinate_result(
        self, text: str, name: str, x: int, y: int,
        ratio_x: float, ratio_y: float, message: str | None = None
    ) -> None:
        if message:
            self._log(message)
            return
        self._log(
            f"Đã chọn tọa độ: {text} -> {name}; pixel=({x}, {y}); "
            f"ratio=({ratio_x:.6f}, {ratio_y:.6f})"
        )

    def _log_ocr_results(
        self, items: list[str], normalized: list[str], locations: list[dict] | None = None
    ) -> None:
        self._log("Kết quả OCR:")
        if not items:
            self._log("Không nhận diện được text đủ tin cậy.")
            return
        locations = locations or []
        for index, text in enumerate(items):
            name = normalized[index] if index < len(normalized) else ""
            element = locations[index] if index < len(locations) else {}
            bounds = element.get("bounds", {})
            x = int(bounds.get("left", 0))
            y = int(bounds.get("top", 0))
            width = int(bounds.get("right", x)) - x
            height = int(bounds.get("bottom", y)) - y
            self._log(f"Rect: ({x}, {y}, {width}, {height})")
            if element.get("matched") and element.get("highlight_bounds"):
                red_bounds = element["highlight_bounds"]
                red_x = int(red_bounds.get("left", 0))
                red_y = int(red_bounds.get("top", 0))
                red_width = int(red_bounds.get("right", red_x)) - red_x
                red_height = int(red_bounds.get("bottom", red_y)) - red_y
                self._log(
                    f"RECT đỏ (khớp): ({red_x}, {red_y}, "
                    f"{red_width}, {red_height})"
                )
            self._log(f"Text-original: {text}")
            self._log(f"Text-chuan hoá: {name}")
            if index < len(items) - 1:
                self._log("---")

    def _selected_device_serial(self):
        return self.device_combo.currentData()

    def _sync_device_list_from_combo(self) -> None:
        self.device_list.blockSignals(True)
        self.device_list.clear()
        for index in range(self.device_combo.count()):
            serial = self.device_combo.itemData(index)
            label = self.device_combo.itemText(index)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, serial)
            self.device_list.addItem(item)
            if index == self.device_combo.currentIndex():
                self.device_list.setCurrentItem(item)
        self.device_list.blockSignals(False)

    def _on_device_list_selection_changed(self, current, _previous=None) -> None:
        if current is None:
            return
        index = self.device_combo.findData(current.data(Qt.ItemDataRole.UserRole))
        if index >= 0 and index != self.device_combo.currentIndex():
            self.device_combo.setCurrentIndex(index)

    def scan_adb_devices(self) -> None:
        current_serial = self.device_combo.currentData()
        self.scan_button.setEnabled(False)
        self.device_list.setEnabled(False)
        self.device_combo.setEnabled(False)
        try:
            devices = AdbClient.list_devices()
            self.device_combo.clear()
            self.device_combo.addItem("Mock-Adb", "mock")
            online_count = 0
            for device in devices:
                serial = device.serial
                try:
                    state = device.get_state()
                except Exception:
                    state = "unavailable"
                online = state == "device"
                status = "đang hoạt động" if online else "mất kết nối"
                self.device_combo.addItem(f"{serial} ({status})", serial)
                if online:
                    online_count += 1

            preferred = current_serial or self._settings.adb_serial or "mock"
            index = self.device_combo.findData(preferred)
            self.device_combo.setCurrentIndex(index if index >= 0 else 0)
            self._sync_device_list_from_combo()
            self._log(f"Quét thiết bị: tìm thấy {online_count} thiết bị online.")
        except Exception as exc:
            self.device_combo.clear()
            self.device_combo.addItem("Mock-Adb", "mock")
            self.device_combo.setCurrentIndex(0)
            self._sync_device_list_from_combo()
            self._log(f"Lỗi quét ADB: {exc}. Vẫn có thể chạy thử.")
        finally:
            self.scan_button.setEnabled(True)
            self.device_list.setEnabled(True)
            self.device_combo.setEnabled(True)

    def _build_tasks_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.task_login = QCheckBox("Đăng nhập (nhập tài khoản khi bắt đầu)")
        self.task_daily_checkin = QCheckBox("Điểm danh")
        self.task_open_activity = QCheckBox("Mở màn hình Hoạt động")
        self.task_receive_quoc_van = QCheckBox("Nhận Lễ Bao Quốc Vận")
        self.task_close_activity = QCheckBox("Tắt màn hình Hoạt động")
        self.task_enter_guild = QCheckBox("Vào quân đoàn")
        self.task_guild_checkin = QCheckBox("Báo danh quân đoàn")
        self.task_receive_lucky_bag = QCheckBox("Nhận túi phúc")
        self.task_guild_fortune = QCheckBox("Cầu vận quân đoàn (5 lần)")
        self.task_enter_strategy = QCheckBox("Vào màn hình Mưu Binh")
        self.task_strategy_defense = QCheckBox("Thiết lập phòng thủ")
        self.task_detect_strategy_status = QCheckBox("Phát hiện trạng thái Mưu Binh")
        self.task_strategy_vuot_ai = QCheckBox("Vượt Ải")
        self.task_receive_strategy_reward = QCheckBox("Nhận thưởng Mưu Binh")
        self.task_close_strategy = QCheckBox("Thoát màn hình Mưu Binh")
        self.task_knb_contribution = QCheckBox("Đóng góp KNB")
        self.task_knb_contribution_count = QSpinBox()
        self.task_knb_contribution_count.setRange(1, 10)
        self.task_knb_contribution_count.setValue(1)
        self.task_knb_contribution_count.setEnabled(False)
        self.task_knb_contribution_count.setKeyboardTracking(False)
        self.task_knb_contribution.toggled.connect(
            self.task_knb_contribution_count.setEnabled
        )
        self.task_territory = QCheckBox("Thăm dò lãnh địa")
        self.task_territory_count = QSpinBox()
        self.task_territory_count.setRange(1, 10)
        self.task_territory_count.setValue(1)
        self.task_territory_count.setEnabled(False)
        self.task_territory_count.setKeyboardTracking(False)
        self.task_territory.toggled.connect(self.task_territory_count.setEnabled)
        self.task_territory_knb = QCheckBox("Mua lượt thiếu bằng KNB")
        self.task_territory_knb.setEnabled(False)
        self.task_territory.toggled.connect(self.task_territory_knb.setEnabled)
        self.task_glass_tower = QCheckBox("Lưu Ly Tháp")
        self.task_glass_tower_count = QSpinBox()
        self.task_glass_tower_count.setRange(6, 10)
        self.task_glass_tower_count.setValue(6)
        self.task_glass_tower_count.setEnabled(False)
        self.task_glass_tower_count.setKeyboardTracking(False)
        self.task_glass_tower.toggled.connect(
            self.task_glass_tower_count.setEnabled
        )
        self.task_glass_tower_knb = QCheckBox("Mua lượt thiếu bằng KNB")
        self.task_glass_tower_knb.setEnabled(False)
        self.task_glass_tower.toggled.connect(
            self.task_glass_tower_knb.setEnabled
        )
        self.task_battle = QCheckBox("Giao tranh")
        self.task_battle_count = QSpinBox()
        self.task_battle_count.setRange(1, 60)
        self.task_battle_count.setValue(15)
        self.task_battle_count.setEnabled(False)
        self.task_battle_count.setKeyboardTracking(False)
        self.task_battle.toggled.connect(self.task_battle_count.setEnabled)
        self.task_battle.toggled.connect(self._toggle_task_battle_options)

        # Giao tranh options are independent from the Daily tab settings.
        self.task_battle_lower_merit = QCheckBox("Hạ chiến công")
        self.task_battle_merit_target = QSpinBox()
        self.task_battle_merit_target.setRange(200, 4000)
        self.task_battle_merit_target.setValue(200)
        self.task_battle_merit_target.setKeyboardTracking(False)
        self.task_battle_merit_target.setEnabled(False)
        self.task_battle_lower_merit.toggled.connect(
            self.task_battle_merit_target.setEnabled
        )
        self.task_battle_npc_house = QCheckBox("Chọn nhà NPC")
        self.task_battle_use_bazhen = QCheckBox("Sử dụng Canh Bát Trân")
        self.task_battle_fast_one_flag = QCheckBox("Nhanh 1 cờ")
        self.task_battle_three_flags = QCheckBox("Bình thường 3 cờ")
        self.task_battle_time_mode = QCheckBox("Thời gian tối đa:")
        self.task_battle_mode_group = QButtonGroup(self)
        self.task_battle_mode_group.setExclusive(True)
        self.task_battle_mode_group.addButton(self.task_battle_fast_one_flag)
        self.task_battle_mode_group.addButton(self.task_battle_three_flags)
        self.task_battle_mode_group.addButton(self.task_battle_time_mode)
        self.task_battle_three_flags.setChecked(True)
        self.task_battle_time_limit = QSpinBox()
        self.task_battle_time_limit.setRange(15, 180)
        self.task_battle_time_limit.setValue(15)
        self.task_battle_time_limit.setSuffix(" giây")
        self.task_battle_time_limit.setKeyboardTracking(False)
        self.task_battle_time_limit.setEnabled(False)
        self.task_battle_time_mode.toggled.connect(
            self.task_battle_time_limit.setEnabled
        )
        self.task_battle_mode_description = QLabel()
        self.task_battle_mode_description.setWordWrap(True)
        self.task_battle_fast_one_flag.toggled.connect(
            self._update_task_battle_mode_description
        )
        self.task_battle_three_flags.toggled.connect(
            self._update_task_battle_mode_description
        )
        self.task_battle_time_mode.toggled.connect(
            self._update_task_battle_mode_description
        )
        self.task_battle_lower_merit.toggled.connect(
            self._toggle_task_battle_merit_mode
        )
        self._update_task_battle_mode_description()
        self.task_championship = QCheckBox("Tranh bá")
        self.task_championship_count = QSpinBox()
        self.task_championship_count.setRange(1, 15)
        self.task_championship_count.setValue(6)
        self.task_championship_count.setEnabled(False)
        self.task_championship_count.setKeyboardTracking(False)
        self.task_championship.toggled.connect(
            self.task_championship_count.setEnabled
        )
        self.task_championship_knb = QCheckBox("Mua lượt bằng KNB")
        self.task_championship_knb.setEnabled(False)
        self.task_championship.toggled.connect(
            self.task_championship_knb.setEnabled
        )
        self.task_championship_fast_one_flag = QCheckBox("Nhanh 1 cờ")
        self.task_championship_four_flags = QCheckBox("Bình thường 4 cờ")
        self.task_championship_time_mode = QCheckBox("Thời gian tối đa:")
        self.task_championship_mode_group = QButtonGroup(self)
        self.task_championship_mode_group.setExclusive(True)
        self.task_championship_mode_group.addButton(
            self.task_championship_fast_one_flag
        )
        self.task_championship_mode_group.addButton(
            self.task_championship_four_flags
        )
        self.task_championship_mode_group.addButton(
            self.task_championship_time_mode
        )
        self.task_championship_four_flags.setChecked(True)
        self.task_championship_time_limit = QSpinBox()
        self.task_championship_time_limit.setRange(15, 180)
        self.task_championship_time_limit.setValue(15)
        self.task_championship_time_limit.setSuffix(" giây")
        self.task_championship_time_limit.setKeyboardTracking(False)
        self.task_championship_time_limit.setEnabled(False)
        self.task_championship_time_mode.toggled.connect(
            self.task_championship_time_limit.setEnabled
        )
        self.task_championship_mode_description = QLabel()
        self.task_championship_mode_description.setWordWrap(True)
        self.task_championship_fast_one_flag.toggled.connect(
            self._update_task_championship_mode_description
        )
        self.task_championship_four_flags.toggled.connect(
            self._update_task_championship_mode_description
        )
        self.task_championship_time_mode.toggled.connect(
            self._update_task_championship_mode_description
        )
        self.task_championship.toggled.connect(
            self._toggle_task_championship_options
        )
        self._update_task_championship_mode_description()
        self._toggle_task_championship_options(
            self.task_championship.isChecked()
        )

        daily_group = QGroupBox("Nhiệm vụ")
        daily_layout = QVBoxLayout(daily_group)
        daily_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        daily_layout.setSpacing(6)

        # Keep account session actions adjacent at the top of the task list.
        for task_checkbox in (
            self.task_login,
            self.doi_tai_khoan_task,
        ):
            daily_layout.addWidget(task_checkbox)

        activity_group = QGroupBox("Hoạt động")
        activity_layout = QVBoxLayout(activity_group)
        activity_layout.addWidget(self.task_open_activity)

        phuc_loi_group = QGroupBox("Phúc Lợi")
        phuc_loi_layout = QVBoxLayout(phuc_loi_group)
        phuc_loi_layout.addWidget(self.task_receive_quoc_van)
        phuc_loi_layout.addWidget(self.task_daily_checkin)
        activity_layout.addWidget(phuc_loi_group)
        activity_layout.addWidget(self.task_close_activity)
        daily_layout.addWidget(activity_group)

        guild_group = QGroupBox("Quân đoàn")
        guild_layout = QVBoxLayout(guild_group)
        for task_checkbox in (
            self.task_enter_guild,
            self.task_guild_checkin,
            self.task_receive_lucky_bag,
            self.task_guild_fortune,
            self.thoat_quan_doan_task,
        ):
            guild_layout.addWidget(task_checkbox)
        daily_layout.addWidget(guild_group)

        strategy_tasks_group = QGroupBox("Mưu Binh")
        strategy_tasks_layout = QVBoxLayout(strategy_tasks_group)
        for task_checkbox in (
            self.task_enter_strategy,
            self.task_strategy_defense,
            self.task_detect_strategy_status,
            self.task_strategy_vuot_ai,
            self.task_receive_strategy_reward,
            self.task_close_strategy,
        ):
            strategy_tasks_layout.addWidget(task_checkbox)
        daily_layout.addWidget(strategy_tasks_group)

        knb_contribution_row = QHBoxLayout()
        knb_contribution_row.addWidget(self.task_knb_contribution)
        knb_contribution_row.addWidget(QLabel("Số lần:"))
        knb_contribution_row.addWidget(self.task_knb_contribution_count)
        knb_contribution_row.addStretch(1)
        daily_layout.addLayout(knb_contribution_row)

        territory_row = QHBoxLayout()
        territory_row.addWidget(self.task_territory)
        territory_row.addWidget(QLabel("Số lần:"))
        territory_row.addWidget(self.task_territory_count)
        territory_row.addWidget(self.task_territory_knb)
        territory_row.addStretch(1)
        daily_layout.addLayout(territory_row)

        glass_tower_row = QHBoxLayout()
        glass_tower_row.addWidget(self.task_glass_tower)
        glass_tower_row.addWidget(QLabel("Số lần:"))
        glass_tower_row.addWidget(self.task_glass_tower_count)
        glass_tower_row.addWidget(self.task_glass_tower_knb)
        glass_tower_row.addStretch(1)
        daily_layout.addLayout(glass_tower_row)

        battle_row = QHBoxLayout()
        battle_row.addWidget(self.task_battle)
        battle_row.addWidget(QLabel("Số trận:"))
        battle_row.addWidget(self.task_battle_count)
        battle_row.addStretch(1)
        daily_layout.addLayout(battle_row)

        task_battle_options = QGridLayout()
        task_battle_options.setContentsMargins(20, 0, 0, 0)
        task_battle_options.setHorizontalSpacing(12)
        task_battle_options.setVerticalSpacing(4)
        merit_row = QHBoxLayout()
        merit_row.addWidget(self.task_battle_lower_merit)
        merit_row.addWidget(QLabel("Chiến công cần hạ:"))
        merit_row.addWidget(self.task_battle_merit_target)
        merit_row.addStretch(1)
        task_battle_options.addLayout(merit_row, 0, 0, 1, 4)
        task_battle_options.addWidget(self.task_battle_npc_house, 1, 0)
        task_battle_options.addWidget(self.task_battle_use_bazhen, 1, 1)
        task_battle_mode_row = self._build_mode_row(
            self.task_battle_fast_one_flag,
            self.task_battle_three_flags,
            self.task_battle_time_mode,
            self.task_battle_time_limit,
        )
        task_battle_options.addWidget(task_battle_mode_row, 2, 0, 1, 4)
        task_battle_options.addWidget(self.task_battle_mode_description, 3, 0, 1, 4)
        daily_layout.addLayout(task_battle_options)

        championship_row = QHBoxLayout()
        championship_row.addWidget(self.task_championship)
        championship_row.addWidget(QLabel("Số trận:"))
        championship_row.addWidget(self.task_championship_count)
        championship_row.addWidget(self.task_championship_knb)
        championship_row.addStretch(1)
        daily_layout.addLayout(championship_row)

        championship_options = QGridLayout()
        championship_options.setContentsMargins(20, 0, 0, 0)
        championship_options.setHorizontalSpacing(12)
        championship_options.setVerticalSpacing(4)
        championship_mode_row = self._build_mode_row(
            self.task_championship_fast_one_flag,
            self.task_championship_four_flags,
            self.task_championship_time_mode,
            self.task_championship_time_limit,
        )
        championship_options.addWidget(championship_mode_row, 0, 0, 1, 4)
        championship_options.addWidget(
            self.task_championship_mode_description, 1, 0, 1, 4
        )
        daily_layout.addLayout(championship_options)


        layout.addWidget(daily_group)

        coordinate_group = QGroupBox("Click theo tọa độ")
        coordinate_layout = QHBoxLayout(coordinate_group)
        self.task_click_coordinates = QCheckBox("Click")
        self.task_click_x = QSpinBox()
        self.task_click_x.setRange(0, 10000)
        self.task_click_x.setPrefix("X: ")
        self.task_click_x.setKeyboardTracking(False)
        self.task_click_y = QSpinBox()
        self.task_click_y.setRange(0, 10000)
        self.task_click_y.setPrefix("Y: ")
        self.task_click_y.setKeyboardTracking(False)
        self.task_click_x.setEnabled(False)
        self.task_click_y.setEnabled(False)
        self.task_click_coordinates.toggled.connect(self.task_click_x.setEnabled)
        self.task_click_coordinates.toggled.connect(self.task_click_y.setEnabled)
        coordinate_layout.addWidget(self.task_click_coordinates)
        coordinate_layout.addWidget(self.task_click_x)
        coordinate_layout.addWidget(self.task_click_y)
        coordinate_layout.addStretch(1)
        layout.addWidget(coordinate_group)

        note = QLabel(
            "Chọn một hoặc nhiều tác vụ rồi nhấn ▶ Bắt đầu. "
            "Cần chọn đúng thiết bị ADB và đang ở trong game. "
            "“Thoát màn hình Quân đoàn” chỉ đóng giao diện, không rời quân đoàn."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return self._make_scrollable_tab(page)

    def _current_config(self) -> dict:
        if self.tabs.currentWidget() is self.clone_tab:
            return self.clone_tab.current_config()
        if self.tabs.tabText(self.tabs.currentIndex()) == "Tác vụ":
            config = self._game_config()
            config.update({
                "utility_tasks_mode": True,
                "task_login": self.task_login.isChecked(),
                "task_open_activity": self.task_open_activity.isChecked(),
                "task_close_activity": self.task_close_activity.isChecked(),
                "task_close_guild": self.thoat_quan_doan_task.isChecked(),
                "task_enter_guild": self.task_enter_guild.isChecked(),
                "task_receive_lucky_bag": self.task_receive_lucky_bag.isChecked(),
                "task_guild_fortune": self.task_guild_fortune.isChecked(),
                "task_enter_strategy": self.task_enter_strategy.isChecked(),
                "task_strategy_defense": self.task_strategy_defense.isChecked(),
                "task_detect_strategy_status": self.task_detect_strategy_status.isChecked(),
                "task_strategy_vuot_ai": self.task_strategy_vuot_ai.isChecked(),
                "task_receive_strategy_reward": self.task_receive_strategy_reward.isChecked(),
                "task_close_strategy": self.task_close_strategy.isChecked(),
                "task_switch_account": self.doi_tai_khoan_task.isChecked(),
                "task_click_coordinates": self.task_click_coordinates.isChecked(),
                "task_click_x": self.task_click_x.value(),
                "task_click_y": self.task_click_y.value(),
                "diem_danh": self.task_daily_checkin.isChecked(),
                "nhan_le_bao_quoc_van": self.task_receive_quoc_van.isChecked(),
                "bao_danh_quan_doan": self.task_guild_checkin.isChecked(),
                "dong_gop_knb": self.task_knb_contribution.isChecked(),
                "so_lan_dong_gop_knb": self.task_knb_contribution_count.value(),
                "tham_do_lanh_dia": self.task_territory.isChecked(),
                "so_lan_tham_do_lanh_dia": self.task_territory_count.value(),
                "tham_do_lanh_dia_knb": self.task_territory_knb.isChecked(),
                "nhiem_vu_luu_ly_thap": self.task_glass_tower.isChecked(),
                "so_lan_luu_ly_thap": self.task_glass_tower_count.value(),
                "luu_ly_thap_knb": self.task_glass_tower_knb.isChecked(),
                "thuc_hien_giao_tranh": self.task_battle.isChecked(),
                "giao_tranh": self.task_battle_count.value(),
                "ha_chien_cong": self.task_battle_lower_merit.isChecked(),
                "chien_cong": self.task_battle_merit_target.value(),
                "chon_nha_npc": (
                    self.task_battle_npc_house.isChecked()
                    and not self.task_battle_lower_merit.isChecked()
                ),
                "giao_tranh_nhanh_1_co": (
                    self.task_battle_fast_one_flag.isChecked()
                    and not self.task_battle_lower_merit.isChecked()
                ),
                "ba_co": (
                    self.task_battle_three_flags.isChecked()
                    and not self.task_battle_lower_merit.isChecked()
                ),
                "thoi_gian_giao_tranh": (
                    self.task_battle_time_limit.value()
                    if (
                        self.task_battle_time_mode.isChecked()
                        and not self.task_battle_lower_merit.isChecked()
                    )
                    else None
                ),
                "su_dung_canh_bat_tran": (
                    self.task_battle_use_bazhen.isChecked()
                    and not self.task_battle_lower_merit.isChecked()
                ),
                "thuc_hien_tranh_ba": self.task_championship.isChecked(),
                "tranh_ba": self.task_championship_count.value(),
                "mua_luot_knb": (
                    self.task_championship_knb.isChecked()
                    and self.task_championship.isChecked()
                ),
                "tranh_ba_fast_mode": (
                    1 if self.task_championship_fast_one_flag.isChecked()
                    else 4
                ),
                "thoi_gian_tranh_ba": (
                    self.task_championship_time_limit.value()
                    if (
                        self.task_championship_time_mode.isChecked()
                        and self.task_championship.isChecked()
                    )
                    else None
                ),
            })
            return config
        if self.tabs.tabText(self.tabs.currentIndex()) == "Mưu Binh":
            config = self._game_config()
            config.update({
                "strategy_mode": True,
                "thiet_lap_muu_binh": self.thiet_lap_muu_binh.isChecked(),
                "vuot_ai_muu_binh": self.vuot_ai_muu_binh.isChecked(),
            })
            return config
        return self._game_config()

    def _game_config(self) -> dict:
        if self.ha_chien_cong.isChecked():
            giao_tranh_mode = {
                "ha_chien_cong": True,
                "chien_cong": self.chien_cong.value(),
                "chon_nha_npc": False,
                "giao_tranh_nhanh_1_co": False,
                "ba_co": False,
                "thoi_gian_giao_tranh": None,
                "su_dung_canh_bat_tran": False,
            }
        else:
            giao_tranh_mode = {
                "ha_chien_cong": False,
                "chien_cong": self.chien_cong.value(),
                "chon_nha_npc": self.chon_nha_npc.isChecked(),
                "giao_tranh_nhanh_1_co": self.giao_tranh_nhanh_1_co.isChecked(),
                "ba_co": self.ba_co.isChecked(),
                "thoi_gian_giao_tranh": (
                    self.thoi_gian_giao_tranh.value()
                    if self.thoi_gian_mode.isChecked()
                    else None
                ),
                "su_dung_canh_bat_tran": self.su_dung_canh_bat_tran.isChecked(),
            }

        if self.tranh_ba_1_co.isChecked():
            tranh_ba_fast_mode = 1
        else:
            tranh_ba_fast_mode = 4

        return {
            "thuc_hien_giao_tranh": self.giao_tranh_group.isChecked(),
            "giao_tranh": self.giao_tranh.value(),
            **giao_tranh_mode,
            "thuc_hien_tranh_ba": self.tranh_ba_group.isChecked(),
            "tranh_ba": self.tranh_ba.value(),
            "mua_luot_knb": self.mua_luot_knb.isChecked(),
            "tranh_ba_fast_mode": tranh_ba_fast_mode,
            "thoi_gian_tranh_ba": (
                self.tranh_ba_thoi_gian.value()
                if self.tranh_ba_thoi_gian_mode.isChecked()
                else None
            ),
            "diem_danh": self.diem_danh.isChecked(),
            "bao_danh_quan_doan": self.bao_danh_quan_doan.isChecked(),
            "dong_gop_knb": self.dong_gop_knb.isChecked(),
            "so_lan_dong_gop_knb": self.so_lan_dong_gop_knb.value(),
            "tham_do_lanh_dia": self.tham_do_lanh_dia.isChecked(),
            "so_lan_tham_do_lanh_dia": self.so_lan_tham_do_lanh_dia.value(),
            "tham_do_lanh_dia_knb": self.tham_do_lanh_dia_knb.isChecked(),
            "nhiem_vu_luu_ly_thap": self.nhiem_vu_luu_ly_thap.isChecked(),
            "so_lan_luu_ly_thap": self.so_lan_luu_ly_thap.value(),
            "luu_ly_thap_knb": self.luu_ly_thap_knb.isChecked(),
        }

    def _prompt_login_credentials(self) -> tuple[str, str] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Đăng nhập")
        form = QFormLayout(dialog)
        username = QLineEdit(dialog)
        username.setPlaceholderText("Nhập username")
        password = QLineEdit(dialog)
        password.setEchoMode(QLineEdit.EchoMode.Password)
        password.setPlaceholderText("Nhập password")
        form.addRow("Username:", username)
        form.addRow("Password:", password)
        buttons = QHBoxLayout()
        ok_button = QPushButton("Đăng nhập", dialog)
        cancel_button = QPushButton("Hủy", dialog)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        user, secret = username.text().strip(), password.text()
        if not user or not secret:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập cả username và password.")
            return None
        return user, secret

    def _set_settings_enabled(self, enabled: bool) -> None:
        """Lock settings during a run, then restore each control's prior enabled state."""
        self.tabs.tabBar().setEnabled(enabled)
        widget_types = (QCheckBox, QSpinBox, QComboBox, QRadioButton, QAbstractButton)
        widgets = set()
        for widget_type in widget_types:
            widgets.update(self.tabs.findChildren(widget_type))
        widgets.update(
            group for group in self.tabs.findChildren(QGroupBox)
            if group.isCheckable()
        )

        if not enabled:
            # Capture explicit enabled states before disabling anything. This keeps
            # dependent controls disabled after a run if their parent task is off.
            self._settings_lock_states = {
                widget: widget.isEnabled() for widget in widgets
            }
            for widget in widgets:
                widget.setEnabled(False)
            return

        for widget in widgets:
            widget.setEnabled(self._settings_lock_states.get(widget, True))
        self._settings_lock_states.clear()

    def start_bot(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        mock_mode = self.device_combo.currentData() == "mock"
        serial = self.device_combo.currentData()
        if not mock_mode and not serial:
            QMessageBox.warning(
                self,
                "Chưa chọn thiết bị",
                "Hãy chuyển sang chế độ ADB, mở LDPlayer, nhấn Quét ADB "
                "và chọn thiết bị cần chạy.",
            )
            return

        config = self._current_config()
        if config.get("task_login"):
            credentials = self._prompt_login_credentials()
            if credentials is None:
                return
            config["login_username"], config["login_password"] = credentials
        if config.get("utility_tasks_mode") and not any(
            config.get(key) for key in (
                "task_login", "task_open_activity", "task_close_activity",
                "task_close_guild", "task_switch_account",
                "task_enter_guild", "task_receive_lucky_bag", "task_guild_fortune",
                "diem_danh", "nhan_le_bao_quoc_van", "bao_danh_quan_doan", "dong_gop_knb",
                "tham_do_lanh_dia", "nhiem_vu_luu_ly_thap",
                "thuc_hien_giao_tranh", "thuc_hien_tranh_ba",
                "task_enter_strategy", "task_strategy_defense",
                "task_detect_strategy_status", "task_strategy_vuot_ai",
                "task_receive_strategy_reward", "task_close_strategy",
                "task_click_coordinates",
            )
        ):
            QMessageBox.warning(
                self, "Chưa chọn tác vụ",
                "Hãy chọn ít nhất một tác vụ trong tab Tác vụ.",
            )
            return
        self._active_clone_mode = bool(config.get("clone_mode"))
        self._active_mock_mode = mock_mode
        self._clone_total_accounts = 0
        if self._active_clone_mode:
            account_file = config.get("clone_account_file", "")
            try:
                accounts = load_accounts(account_file)
            except (OSError, UnicodeError, ValueError) as exc:
                QMessageBox.warning(
                    self,
                    "Danh sách tài khoản không hợp lệ",
                    str(exc),
                )
                return
            self._clone_total_accounts = len(accounts)
            selected_tasks = [
                key for key in (
                    "clone_login",
                    "clone_daily_check_in",
                    "clone_guild_check_in",
                    "clone_receive_lucky_bag",
                    "clone_guild_fortune",
                    "clone_logout",
                ) if config.get(key)
            ]
            if not selected_tasks:
                QMessageBox.warning(
                    self,
                    "Chưa chọn nhiệm vụ",
                    "Hãy chọn ít nhất một nhiệm vụ trong tab Clone.",
                )
                return
            self._log(
                f"Tab Clone: đã nạp {len(accounts)} tài khoản. "
                "Mật khẩu không được ghi vào nhật ký."
            )
        from dctq_auto.gui.workers import BotWorker
        self._worker = BotWorker(
            serial=serial,
            screenshot_dir=self._settings.screenshot_dir,
            config=config,
            mock_mode=mock_mode,
            parent=self,
        )
        self._worker.log_message.connect(self._log)
        self._worker.progress_changed.connect(self._update_progress)
        self._worker.task_progress_changed.connect(self._update_task_progress)
        self._worker.clone_account_result.connect(self._update_clone_account_result)
        self._init_task_progress(config)
        self._worker.finished.connect(self._on_worker_finished)
        self._set_settings_enabled(False)
        self.device_combo.setEnabled(False)
        self.scan_button.setEnabled(False)
        self._paused = False
        self._run_started_at = time.monotonic()
        self._pause_started_at = None
        self._paused_duration = 0.0
        self.current_activity_label.setText("Đang xử lý: Chuẩn bị…")
        if self._active_clone_mode:
            self.progress_bar.setRange(0, max(1, self._clone_total_accounts))
            self.progress_bar.setFormat("%v/%m (%p%)")
            self.progress_bar.setValue(0)
            self.clone_result_list.clear()
            for account in accounts:
                item = QListWidgetItem(account.username)
                item.setIcon(self._status_icon("·", "#6e7781"))
                item.setData(Qt.ItemDataRole.UserRole, account.username)
                self.clone_result_list.addItem(item)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setFormat("%v/%m (%p%)")
            self.progress_bar.setValue(0)
        self.elapsed_time_label.setText("Thời gian đã chạy: 00:00:00")
        self.eta_label.setText("Dự kiến kết thúc: Chưa ước tính")
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("⏸")
        self.pause_button.setToolTip("Tạm dừng")
        self.stop_button.setEnabled(True)
        self.elapsed_timer.start()
        if mock_mode:
            self._log("Đang chạy thử; không gửi lệnh ADB.")
        else:
            self._log(f"Đang chạy tác vụ nền trên thiết bị {serial}…")
        self._worker.start()

    def toggle_pause_bot(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        if self._paused:
            self.resume_bot()
        else:
            self.pause_bot()

    def pause_bot(self) -> None:
        if self._worker is None or not self._worker.isRunning() or self._paused:
            return
        self._worker.pause()
        self._paused = True
        self._pause_started_at = time.monotonic()
        self.pause_button.setText("▶")
        self.pause_button.setToolTip("Tiếp tục")
        self._log("Đã tạm dừng tại điểm an toàn; nhấn Tiếp tục để chạy tiếp.")

    def resume_bot(self) -> None:
        if self._worker is None or not self._worker.isRunning() or not self._paused:
            return
        now = time.monotonic()
        if self._pause_started_at is not None:
            self._paused_duration += now - self._pause_started_at
        self._pause_started_at = None
        self._paused = False
        self._worker.resume()
        self.pause_button.setText("⏸")
        self.pause_button.setToolTip("Tạm dừng")
        self._log("Tiếp tục tác vụ.")

    def stop_bot(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.resume()
            self._worker.requestInterruption()
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self._log("Đã gửi yêu cầu dừng hẳn; worker sẽ dừng tại điểm kiểm tra tiếp theo.")

    @staticmethod
    def _task_specs(config: dict) -> list[tuple[str, int]]:
        """Return progress rows using the exact labels emitted by the worker."""
        if config.get("utility_tasks_mode"):
            task_labels = (
                ("task_login", "Đăng nhập"),
                ("diem_danh", "Điểm danh"),
                ("task_enter_guild", "Vào quân đoàn"),
                ("bao_danh_quan_doan", "Báo danh quân đoàn"),
                ("task_receive_lucky_bag", "Nhận túi phúc"),
                ("task_guild_fortune", "Cầu vận quân đoàn (5 lần)"),
                ("dong_gop_knb", "Đóng góp KNB"),
                ("tham_do_lanh_dia", "Thăm dò lãnh địa"),
                ("nhiem_vu_luu_ly_thap", "Lưu Ly Tháp"),
                ("thuc_hien_giao_tranh", "Giao tranh"),
                ("thuc_hien_tranh_ba", "Tranh bá"),
                ("thiet_lap_muu_binh", "Mưu binh"),
                ("task_close_guild", "Thoát màn hình Quân đoàn"),
                ("task_switch_account", "Đổi tài khoản"),
                ("task_click_coordinates", "Click theo tọa độ"),
            )
            return [(label, 1) for key, label in task_labels if config.get(key)]
        from dctq_auto.tasks.registry import get_enabled_tasks
        return [(spec.label, count) for spec, count in get_enabled_tasks(config)]

    def _init_task_progress(self, config: dict) -> None:
        self.task_progress_list.clear()
        self.task_progress_labels.clear()
        is_clone = bool(config.get("clone_mode"))
        self.clone_result_list.clear()
        self.clone_result_list.setVisible(is_clone)
        self.task_progress_list.setVisible(not is_clone)
        if is_clone:
            return
        for name, count in self._task_specs(config):
            item = QListWidgetItem()
            self.task_progress_list.addItem(item)
            self.task_progress_labels[name] = item
            self._render_task_progress(name, "pending", 0, count)

    @staticmethod
    def _status_icon(glyph: str, color: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor(color))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, glyph)
        painter.end()
        return QIcon(pixmap)

    def _render_task_progress(self, name: str, state: str, completed: int, total: int) -> None:
        item = self.task_progress_labels.get(name)
        if item is None:
            return
        if state == "done":
            item.setIcon(self._status_icon("✓", "#22863a"))
            prefix = ""
        elif state == "failed":
            item.setIcon(self._status_icon("✗", "#d1242f"))
            prefix = ""
        elif state == "running":
            item.setIcon(self._status_icon("→", "#0969da"))
            prefix = ""
        else:
            item.setIcon(QIcon())
            prefix = "■ " if state == "stopped" else "· "
        show_count = total > 1 or name == "Thăm dò lãnh địa"
        detail = f" {completed}/{total}" if show_count else ""
        item.setText(f"{prefix}{name}{detail}")
        if state == "running":
            self.task_progress_list.scrollToItem(
                item, QAbstractItemView.ScrollHint.PositionAtCenter
            )

    def _update_clone_account_result(self, username: str, success: bool) -> None:
        icon = (
            self._status_icon("✓", "#22863a")
            if success else self._status_icon("✗", "#d1242f")
        )
        for index in range(self.clone_result_list.count()):
            item = self.clone_result_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == username:
                item.setIcon(icon)
                item.setText(username)
                return
        item = QListWidgetItem(username)
        item.setIcon(icon)
        item.setData(Qt.ItemDataRole.UserRole, username)
        self.clone_result_list.addItem(item)
        self.clone_result_list.scrollToBottom()

    def _update_task_progress(self, name: str, state: str, completed: int, total: int) -> None:
        self._render_task_progress(name, state, completed, total)

    def _update_progress(self, completed: int, total: int, status: str) -> None:
        if self._active_clone_mode:
            self.current_activity_label.setText(f"Đang xử lý: {status}")
            # Account totals live beneath the bar; usernames/details remain in the log.
            self.progress_bar.setRange(0, max(1, self._clone_total_accounts))
            self.progress_bar.setFormat("%v/%m (%p%)")
            self.progress_bar.setValue(
                max(0, min(self._clone_total_accounts, completed))
            )
            # Per-account results are shown in the scrollable list.
            return
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setFormat("%v/%m (%p%)")
        self.progress_bar.setValue(max(0, min(max(1, total), completed)))

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _update_elapsed_time(self) -> None:
        if self._run_started_at is None:
            return
        now = time.monotonic()
        paused_duration = self._paused_duration
        if self._paused and self._pause_started_at is not None:
            paused_duration += now - self._pause_started_at
        elapsed = now - self._run_started_at - paused_duration
        self.elapsed_time_label.setText(
            f"Thời gian đã chạy: {self._format_duration(elapsed)}"
        )

    def _on_worker_finished(self) -> None:
        self.elapsed_timer.stop()
        self._paused = False
        self._pause_started_at = None
        self._run_started_at = None
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("⏸")
        self.pause_button.setToolTip("Tạm dừng")
        self.stop_button.setEnabled(False)
        self._set_settings_enabled(True)
        self.device_combo.setEnabled(True)
        self._on_device_changed()
        if self.progress_bar.value() < 100:
            for name, label in self.task_progress_labels.items():
                if label.text().startswith("→"):
                    self._render_task_progress(name, "stopped", 0, 1)
                    break
        self._log("Worker đã kết thúc.")

    def _log(self, message: str) -> None:
        """Send activity messages to the console/logger; the GUI has no log panel."""
        logging.getLogger(__name__).info(message)
