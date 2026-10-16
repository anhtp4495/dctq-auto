"""Main PySide6 window with task tabs and shared controls."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
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
        self.resize(700, 600)
        self._settings = Settings.from_env()
        self._worker: BotWorker | None = None

        central = QWidget(self)
        root = QVBoxLayout(central)

        adb_group = QGroupBox("Thiết bị ADB")
        adb_layout = QHBoxLayout(adb_group)
        adb_layout.addWidget(QLabel("LDPlayer:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(280)
        self.device_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.device_combo.setMinimumContentsLength(24)
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
        self.ba_co = QCheckBox("3 cờ")
        self.su_dung_canh_bat_tran = QCheckBox("Sử dụng Canh Bát Trân")
        self.ha_chien_cong = QCheckBox("Hạ chiến công")
        self.chien_cong = QSpinBox()
        self.chien_cong.setRange(1, 999999)
        self.chien_cong.setValue(1)
        self.chien_cong.setKeyboardTracking(False)
        self.chien_cong.editingFinished.connect(self.chien_cong.clearFocus)

        self.giao_tranh_options = QWidget()
        options_layout = QGridLayout(self.giao_tranh_options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setHorizontalSpacing(16)
        options_layout.setVerticalSpacing(4)
        options_layout.addWidget(self.chon_nha_npc, 0, 0)
        options_layout.addWidget(self.ba_co, 0, 1)
        options_layout.addWidget(self.su_dung_canh_bat_tran, 0, 2)

        self.chien_cong_row = QWidget()
        chien_cong_layout = QHBoxLayout(self.chien_cong_row)
        chien_cong_layout.setContentsMargins(0, 0, 0, 0)
        chien_cong_layout.addWidget(QLabel("Chiến công cần hạ:"))
        chien_cong_layout.addWidget(self.chien_cong)
        chien_cong_layout.addStretch(1)
        self.chien_cong.setEnabled(False)
        self.ha_chien_cong.toggled.connect(self._toggle_chien_cong_mode)

        self.mua_luot_knb = QCheckBox("Mua lượt bằng KNB (Kim Nguyên Bảo)")
        self.mua_luot_knb.setChecked(False)
        self.tranh_ba_0_co = QRadioButton("Nhanh 0 cờ")
        self.tranh_ba_1_co = QRadioButton("Nhanh 1 cờ")
        self.tranh_ba_4_co = QRadioButton("Bình thường 4 cờ")
        self.tranh_ba_0_co.setChecked(True)

        self.diem_danh = QCheckBox("Thực hiện điểm danh")
        self.diem_danh.setChecked(True)
        self.bao_danh_quan_doan = QCheckBox("Thực hiện báo danh quân đoàn")
        self.bao_danh_quan_doan.setChecked(True)
        self.thiet_lap_muu_binh = QCheckBox("Thiết lập mưu binh")
        self.thiet_lap_muu_binh.setChecked(True)

        self.tabs.addTab(self._build_daily_tab(), "Nhiệm vụ hằng ngày")
        self.tabs.addTab(self._build_strategy_tab(), "Mưu binh")
        self.tabs.addTab(self._build_war_tab(), "Quốc chiến")

        controls = QHBoxLayout()
        self.start_button = QPushButton("Bắt đầu")
        self.stop_button = QPushButton("Dừng")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_bot)
        self.stop_button.clicked.connect(self.stop_bot)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        root.addLayout(controls)

        log_group = QGroupBox("Nhật ký hoạt động")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Nhật ký sẽ hiển thị tại đây.")
        log_layout.addWidget(self.log_view)
        root.addWidget(log_group, 1)

        self.setCentralWidget(central)
        self.scan_adb_devices()
        self._log("Ứng dụng đã khởi động. Logic gameplay chưa được triển khai.")

    def _build_daily_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        giao_tranh_group = QGroupBox("Giao tranh")
        giao_tranh_layout = QVBoxLayout(giao_tranh_group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số trận:"))
        row.addStretch(1)
        self.giao_tranh.setMinimumWidth(120)
        row.addWidget(self.giao_tranh)
        giao_tranh_layout.addLayout(row)
        giao_tranh_layout.addWidget(self.ha_chien_cong)
        giao_tranh_layout.addWidget(self.giao_tranh_options)
        giao_tranh_layout.addWidget(self.chien_cong_row)
        layout.addWidget(giao_tranh_group)

        tranh_ba_group = QGroupBox("Tranh bá")
        tranh_ba_layout = QVBoxLayout(tranh_ba_group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số trận:"))
        row.addStretch(1)
        self.tranh_ba.setMinimumWidth(120)
        row.addWidget(self.tranh_ba)
        tranh_ba_layout.addLayout(row)
        tranh_ba_layout.addWidget(self.mua_luot_knb)
        fast_mode_row = QHBoxLayout()
        fast_mode_row.addWidget(QLabel("Chế độ nhanh:"))
        fast_mode_row.addWidget(self.tranh_ba_0_co)
        fast_mode_row.addWidget(self.tranh_ba_1_co)
        fast_mode_row.addWidget(self.tranh_ba_4_co)
        fast_mode_row.addStretch(1)
        tranh_ba_layout.addLayout(fast_mode_row)
        layout.addWidget(tranh_ba_group)

        other_group = QGroupBox("Nhiệm vụ khác")
        other_layout = QGridLayout(other_group)
        other_layout.addWidget(self.diem_danh, 0, 0)
        other_layout.addWidget(self.bao_danh_quan_doan, 0, 1)
        layout.addWidget(other_group)

        layout.addStretch(1)
        return page

    def _toggle_chien_cong_mode(self, enabled: bool) -> None:
        self.chon_nha_npc.setEnabled(not enabled)
        self.ba_co.setEnabled(not enabled)
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

    def scan_adb_devices(self) -> None:
        current_serial = self.device_combo.currentData()
        self.scan_button.setEnabled(False)
        self.device_combo.setEnabled(False)
        try:
            devices = AdbClient.list_devices()
            self.device_combo.clear()
            for device in devices:
                serial = device.serial
                try:
                    state = device.get_state()
                except Exception:
                    state = "unavailable"
                if state == "device":
                    self.device_combo.addItem(serial, serial)

            if current_serial:
                index = self.device_combo.findData(current_serial)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)

            if self.device_combo.count() == 0:
                self.device_combo.addItem("Không tìm thấy thiết bị ADB", None)
                self._log("Quét ADB: không tìm thấy thiết bị đang online.")
            else:
                self._log(f"Quét ADB: tìm thấy {self.device_combo.count()} thiết bị.")
                if self._settings.adb_serial:
                    index = self.device_combo.findData(self._settings.adb_serial)
                    if index >= 0:
                        self.device_combo.setCurrentIndex(index)
        except Exception as exc:
            self.device_combo.clear()
            self.device_combo.addItem("Không thể quét ADB", None)
            self._log(f"Lỗi quét ADB: {exc}")
        finally:
            self.scan_button.setEnabled(True)
            self.device_combo.setEnabled(True)

    def _current_config(self) -> dict:
        if self.ha_chien_cong.isChecked():
            giao_tranh_mode = {
                "ha_chien_cong": True,
                "chien_cong": self.chien_cong.value(),
                "chon_nha_npc": False,
                "ba_co": False,
                "su_dung_canh_bat_tran": False,
            }
        else:
            giao_tranh_mode = {
                "ha_chien_cong": False,
                "chien_cong": self.chien_cong.value(),
                "chon_nha_npc": self.chon_nha_npc.isChecked(),
                "ba_co": self.ba_co.isChecked(),
                "su_dung_canh_bat_tran": self.su_dung_canh_bat_tran.isChecked(),
            }

        if self.tranh_ba_1_co.isChecked():
            tranh_ba_fast_mode = 1
        elif self.tranh_ba_4_co.isChecked():
            tranh_ba_fast_mode = 4
        else:
            tranh_ba_fast_mode = 0

        return {
            "giao_tranh": self.giao_tranh.value(),
            **giao_tranh_mode,
            "tranh_ba": self.tranh_ba.value(),
            "mua_luot_knb": self.mua_luot_knb.isChecked(),
            "tranh_ba_fast_mode": tranh_ba_fast_mode,
            "diem_danh": self.diem_danh.isChecked(),
            "bao_danh_quan_doan": self.bao_danh_quan_doan.isChecked(),
            "thiet_lap_muu_binh": self.thiet_lap_muu_binh.isChecked(),
        }

    def start_bot(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        serial = self.device_combo.currentData()
        if not serial:
            QMessageBox.warning(
                self,
                "Chưa chọn thiết bị",
                "Hãy mở LDPlayer, nhấn Quét ADB và chọn thiết bị cần chạy.",
            )
            return

        config = self._current_config()
        self._worker = BotWorker(
            serial=serial,
            screenshot_dir=self._settings.screenshot_dir,
            config=config,
            parent=self,
        )
        self._worker.log_message.connect(self._log)
        self._worker.finished.connect(self._on_worker_finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._log(f"Đang chạy tác vụ nền trên thiết bị {serial}…")
        self._worker.start()

    def stop_bot(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self.stop_button.setEnabled(False)
            self._log("Đã gửi yêu cầu dừng; worker sẽ dừng tại điểm kiểm tra tiếp theo.")

    def _on_worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._log("Worker đã kết thúc.")

    def _log(self, message: str) -> None:
        self.log_view.appendPlainText(message)
        logging.getLogger(__name__).info(message)
