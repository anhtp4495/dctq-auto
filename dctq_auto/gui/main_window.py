"""Main PySide6 window with task tabs and shared controls."""

import logging
import time

from PySide6.QtCore import Qt, QTimer, QSettings, QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QInputDialog,
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
        self.last_screen_short: str | None = None

        central = QWidget(self)
        root = QVBoxLayout(central)

        adb_group = QGroupBox("Thiết bị")
        adb_layout = QHBoxLayout(adb_group)
        adb_layout.addWidget(QLabel("Thiết bị:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(0)
        self.device_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.device_combo.setMinimumContentsLength(10)
        self.device_combo.addItem("Chạy thử (không cần thiết bị)", "mock")
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        adb_layout.addWidget(self.device_combo, 1)
        self.scan_button = QPushButton("Quét ADB")
        self.scan_button.clicked.connect(self.scan_adb_devices)
        adb_layout.addWidget(self.scan_button)
        root.addWidget(adb_group)
        capture_row = QHBoxLayout()
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
        root.addLayout(capture_row)

        self.tabs = QTabWidget(central)
        root.addWidget(self.tabs)

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
        self.thiet_lap_muu_binh = QCheckBox("Thiết lập mưu binh")
        self.thiet_lap_muu_binh.setChecked(True)

        self.tabs.addTab(self._build_daily_tab(), "Nhiệm vụ hằng ngày")
        self.tabs.addTab(self._build_strategy_tab(), "Mưu binh")
        self.tabs.addTab(self._build_war_tab(), "Quốc chiến")
        self.clone_tab = CloneTab()
        self.tabs.addTab(self.clone_tab, "Clone")

        progress_group = QGroupBox("Tiến trình")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)
        self.clone_result_label = QLabel("0 thành công | 0 thất bại")
        self.clone_result_label.setWordWrap(True)
        progress_layout.addWidget(self.clone_result_label)
        self.task_progress_layout = QVBoxLayout()
        self.task_progress_layout.setSpacing(2)
        self.task_progress_labels: dict[str, QLabel] = {}
        progress_layout.addLayout(self.task_progress_layout)
        timing_layout = QHBoxLayout()
        self.elapsed_time_label = QLabel("Thời gian đã chạy: 00:00:00")
        self.eta_label = QLabel("Dự kiến kết thúc: Chưa ước tính")
        timing_layout.addWidget(self.elapsed_time_label)
        timing_layout.addStretch(1)
        timing_layout.addWidget(self.eta_label)
        progress_layout.addLayout(timing_layout)
        root.addWidget(progress_group)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)

        log_group = QGroupBox("Nhật ký hoạt động")
        log_layout = QVBoxLayout(log_group)
        log_header = QHBoxLayout()
        log_header.addStretch(1)
        self.clear_log_button = QPushButton("Xóa nhật ký")
        self.clear_log_button.clicked.connect(self.clear_log)
        log_header.addWidget(self.clear_log_button)
        log_layout.addLayout(log_header)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.log_view.setPlaceholderText("Nhật ký sẽ hiển thị tại đây.")
        log_layout.addWidget(self.log_view)
        log_group.setFixedHeight(210)
        root.addWidget(log_group)

        self.setCentralWidget(central)
        self._restore_settings()
        self._place_window_on_right()
        self._connect_settings_persistence()
        self.tabs.currentChanged.connect(self._save_settings)
        self.clone_tab.account_file_input.textChanged.connect(self._save_settings)
        self._on_device_changed()
        self._log(
            "Ứng dụng đã khởi động. Chọn Chạy thử hoặc một thiết bị ADB."
        )


    def _place_window_on_right(self) -> None:
        """Open as a narrow, full-height utility window on the right side."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(333, 800)
            return
        area = screen.availableGeometry()
        width = min(333, area.width())
        self.setMinimumWidth(min(300, width))
        self.resize(width, area.height())
        self.move(area.right() - width + 1, area.top())

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

        account_file = self._ui_settings.value("clone/account_file", "")
        if hasattr(self, "clone_tab"):
            self.clone_tab.account_file_input.setText(str(account_file or ""))
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
                "clone/account_file", self.clone_tab.account_file_input.text().strip()
            )
            for name, widget in self._clone_settings_widgets().items():
                self._ui_settings.setValue(f"clone/controls/{name}", widget.isChecked())
        self._ui_settings.sync()

    def closeEvent(self, event) -> None:
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

    def _build_strategy_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        group = QGroupBox("Mưu binh")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(self.thiet_lap_muu_binh)
        layout.addWidget(group)
        layout.addStretch(1)
        return page

    @staticmethod
    def _build_war_tab() -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        group = QGroupBox("Quốc chiến")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(QLabel("Sẽ bổ sung cấu hình sau."))
        layout.addWidget(group)
        layout.addStretch(1)
        return page

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
            log_view = self.log_view

            def is_log_or_ancestor(widget: QWidget) -> bool:
                current = log_view
                while current is not None:
                    if current is widget:
                        return True
                    current = current.parentWidget()
                return False

            def is_log_descendant(widget: QWidget) -> bool:
                current = widget.parentWidget()
                while current is not None:
                    if current is log_view:
                        return True
                    current = current.parentWidget()
                return False

            widgets_to_lock = [
                widget for widget in central.findChildren(QWidget)
                if (
                    widget is not self.clear_log_button
                    and not is_log_or_ancestor(widget)
                    and not is_log_descendant(widget)
                )
            ]

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

    def scan_adb_devices(self) -> None:
        current_serial = self.device_combo.currentData()
        self.scan_button.setEnabled(False)
        self.device_combo.setEnabled(False)
        try:
            devices = AdbClient.list_devices()
            self.device_combo.clear()
            self.device_combo.addItem("Chạy thử (không cần thiết bị)", "mock")
            online_count = 0
            for device in devices:
                serial = device.serial
                try:
                    state = device.get_state()
                except Exception:
                    state = "unavailable"
                if state == "device":
                    self.device_combo.addItem(serial, serial)
                    online_count += 1

            preferred = current_serial or self._settings.adb_serial or "mock"
            index = self.device_combo.findData(preferred)
            self.device_combo.setCurrentIndex(index if index >= 0 else 0)
            self._log(f"Quét ADB: tìm thấy {online_count} thiết bị online.")
        except Exception as exc:
            self.device_combo.clear()
            self.device_combo.addItem("Chạy thử (không cần thiết bị)", "mock")
            self.device_combo.setCurrentIndex(0)
            self._log(f"Lỗi quét ADB: {exc}. Vẫn có thể chạy thử.")
        finally:
            self.scan_button.setEnabled(True)
            self.device_combo.setEnabled(True)

    def _current_config(self) -> dict:
        if self.tabs.currentWidget() is self.clone_tab:
            return self.clone_tab.current_config()
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
            "thiet_lap_muu_binh": self.thiet_lap_muu_binh.isChecked(),
        }

    def _set_settings_enabled(self, enabled: bool) -> None:
        """Lock configuration controls and prevent tab switching while a run is active."""
        self.tabs.tabBar().setEnabled(enabled)
        for widget_type in (QCheckBox, QSpinBox, QComboBox, QRadioButton, QAbstractButton):
            for widget in self.tabs.findChildren(widget_type):
                widget.setEnabled(enabled)
        for group in self.tabs.findChildren(QGroupBox):
            if group.isCheckable():
                group.setEnabled(enabled)

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
        self._init_task_progress(config)
        self._worker.finished.connect(self._on_worker_finished)
        self._set_settings_enabled(False)
        self.device_combo.setEnabled(False)
        self.scan_button.setEnabled(False)
        self._paused = False
        self._run_started_at = time.monotonic()
        self._pause_started_at = None
        self._paused_duration = 0.0
        if self._active_clone_mode:
            self.progress_bar.setRange(0, max(1, self._clone_total_accounts))
            self.progress_bar.setFormat("%v/%m tài khoản đã xử lý")
            self.progress_bar.setValue(0)
            self.clone_result_label.setText("0 thành công | 0 thất bại")
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setFormat("%p%")
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
        """Load task definitions only when the user starts a task."""
        from dctq_auto.tasks.registry import get_enabled_tasks
        return [(spec.label, count) for spec, count in get_enabled_tasks(config)]

    def _init_task_progress(self, config: dict) -> None:
        while self.task_progress_layout.count():
            item = self.task_progress_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.task_progress_labels.clear()
        if config.get("clone_mode"):
            # Keep account names out of the progress panel; details go to the activity log.
            task_names = []
        else:
            task_names = self._task_specs(config)
        for name, count in task_names:
            label = QLabel()
            label.setStyleSheet("color: #808080;")
            self.task_progress_layout.addWidget(label)
            self.task_progress_labels[name] = label
            self._render_task_progress(name, "pending", 0, count)

    def _render_task_progress(self, name: str, state: str, completed: int, total: int) -> None:
        label = self.task_progress_labels.get(name)
        if label is None:
            return
        if state == "running":
            prefix, color = "→", "#D97706"
        elif state == "done":
            prefix, color = "✓", "#16A34A"
        elif state == "failed":
            prefix, color = "✗", "#DC2626"
        elif state == "stopped":
            prefix, color = "■", "#DC2626"
        else:
            prefix, color = "·", "#808080"
        show_count = total > 1 or name == "Thăm dò lãnh địa"
        detail = f" {completed}/{total}" if show_count else ""
        label.setText(f"{prefix} {name}{detail}")
        label.setStyleSheet("color: " + color + ";")

    def _update_task_progress(self, name: str, state: str, completed: int, total: int) -> None:
        self._render_task_progress(name, state, completed, total)

    def _update_progress(self, completed: int, total: int, status: str) -> None:
        if self._active_clone_mode:
            # Account totals live beneath the bar; usernames/details remain in the log.
            self.progress_bar.setRange(0, max(1, self._clone_total_accounts))
            self.progress_bar.setValue(
                max(0, min(self._clone_total_accounts, completed))
            )
            self.progress_bar.setFormat("%v/%m tài khoản đã xử lý")
            self.clone_result_label.setText(status or "0 thành công | 0 thất bại")
            return
        percent = int(completed * 100 / total) if total else 0
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setValue(max(0, min(100, percent)))

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

    def clear_log(self) -> None:
        self.log_view.clear()

    def _log(self, message: str) -> None:
        scrollbar = self.log_view.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 1
        previous_value = scrollbar.value()
        self.log_view.appendPlainText(message)
        if not was_at_bottom:
            # Keep the reader's position when new log lines arrive.
            scrollbar.setValue(previous_value)
        logging.getLogger(__name__).info(message)
