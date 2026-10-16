"""Main PySide6 window with task tabs and shared controls."""

import logging
import time

from PySide6.QtCore import Qt, QTimer, QSettings
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
from dctq_auto.gui.workers import BotWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DCTQ Auto")
        self._ui_settings = QSettings("DCTQAuto", "DCTQAuto")
        self._settings = Settings.from_env()
        self._worker: BotWorker | None = None
        self._paused = False
        self._run_started_at: float | None = None
        self._pause_started_at: float | None = None
        self._paused_duration = 0.0

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

        controls = QHBoxLayout()
        self.start_button = QPushButton("Bắt đầu")
        self.pause_button = QPushButton("Tạm dừng")
        self.stop_button = QPushButton("Dừng hẳn")
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_bot)
        self.pause_button.clicked.connect(self.toggle_pause_bot)
        self.stop_button.clicked.connect(self.stop_bot)
        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        root.addLayout(controls)

        progress_group = QGroupBox("Tiến trình")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)
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
        self.log_view.setPlaceholderText("Nhật ký sẽ hiển thị tại đây.")
        log_layout.addWidget(self.log_view)
        log_group.setFixedHeight(210)
        root.addWidget(log_group)

        self.setCentralWidget(central)
        self._restore_settings()
        self._place_window_on_right()
        self._connect_settings_persistence()
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

    def _connect_settings_persistence(self) -> None:
        for widget in self._settings_widgets().values():
            if isinstance(widget, (QCheckBox, QRadioButton, QGroupBox)):
                widget.toggled.connect(self._save_settings)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._save_settings)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._save_settings)

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
        """Lock configuration controls while keeping tabs and scrolling usable."""
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
        self.progress_bar.setValue(0)
        self.elapsed_time_label.setText("Thời gian đã chạy: 00:00:00")
        self.eta_label.setText("Dự kiến kết thúc: Chưa ước tính")
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Tạm dừng")
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
        self.pause_button.setText("Tiếp tục")
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
        self.pause_button.setText("Tạm dừng")
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
        tasks: list[tuple[str, int]] = []
        for key, label in (
            ("diem_danh", "Điểm danh"),
            ("bao_danh_quan_doan", "Báo danh quân đoàn"),
            ("thiet_lap_muu_binh", "Thiết lập mưu binh"),
        ):
            if config.get(key):
                tasks.append((label, 1))
        for key, label, count_key in (
            ("dong_gop_knb", "Đóng góp KNB", "so_lan_dong_gop_knb"),
            ("tham_do_lanh_dia", "Thăm dò lãnh địa", "so_lan_tham_do_lanh_dia"),
            ("nhiem_vu_luu_ly_thap", "Nhiệm vụ Lưu Ly Tháp", "so_lan_luu_ly_thap"),
        ):
            if config.get(key):
                tasks.append((label, int(config.get(count_key, 1))))
        if config.get("thuc_hien_giao_tranh"):
            tasks.append(("Giao tranh", int(config.get("giao_tranh", 1))))
        if config.get("thuc_hien_tranh_ba"):
            tasks.append(("Tranh bá", int(config.get("tranh_ba", 1))))
        return tasks

    def _init_task_progress(self, config: dict) -> None:
        while self.task_progress_layout.count():
            item = self.task_progress_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.task_progress_labels.clear()
        for name, count in self._task_specs(config):
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
        elif state == "stopped":
            prefix, color = "■", "#DC2626"
        else:
            prefix, color = "·", "#808080"
        detail = f" {completed}/{total}" if total > 1 else ""
        label.setText(f"{prefix} {name}{detail}")
        label.setStyleSheet("color: " + color + ";")

    def _update_task_progress(self, name: str, state: str, completed: int, total: int) -> None:
        self._render_task_progress(name, state, completed, total)

    def _update_progress(self, completed: int, total: int, status: str) -> None:
        percent = int(completed * 100 / total) if total else 0
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
        self.pause_button.setText("Tạm dừng")
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
        self.log_view.appendPlainText(message)
        logging.getLogger(__name__).info(message)
