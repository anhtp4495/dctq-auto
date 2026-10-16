"""Main PySide6 window with task tabs and shared controls."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.config.settings import Settings
from dctq_auto.gui.workers import BotWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DCTQ Auto")
        self.resize(640, 520)
        self._settings = Settings.from_env()
        self._worker: BotWorker | None = None

        central = QWidget(self)
        root = QVBoxLayout(central)
        self.tabs = QTabWidget(central)
        root.addWidget(self.tabs)

        self.giao_tranh = QSpinBox()
        self.giao_tranh.setRange(0, 999)
        self.giao_tranh.setValue(15)
        self.tranh_ba = QSpinBox()
        self.tranh_ba.setRange(0, 999)
        self.tranh_ba.setValue(6)
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
        root.addLayout(controls)

        log_group = QGroupBox("Nhật ký hoạt động")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Nhật ký sẽ hiển thị tại đây.")
        log_layout.addWidget(self.log_view)
        root.addWidget(log_group, 1)

        self.setCentralWidget(central)
        self._log("Ứng dụng đã khởi động. Logic gameplay chưa được triển khai.")

    def _build_daily_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for label, control in (
            ("Giao tranh (trận)", self.giao_tranh),
            ("Tranh bá (trận)", self.tranh_ba),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch(1)
            control.setMinimumWidth(120)
            row.addWidget(control)
            layout.addLayout(row)

        layout.addSpacing(12)
        layout.addWidget(self.diem_danh)
        layout.addWidget(self.bao_danh_quan_doan)
        layout.addStretch(1)
        return page

    def _build_strategy_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.thiet_lap_muu_binh)
        layout.addStretch(1)
        return page

    @staticmethod
    def _build_war_tab() -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(QLabel("Tab Quốc chiến — sẽ bổ sung cấu hình sau."))
        layout.addStretch(1)
        return page

    def _current_config(self) -> dict:
        return {
            "giao_tranh": self.giao_tranh.value(),
            "tranh_ba": self.tranh_ba.value(),
            "diem_danh": self.diem_danh.isChecked(),
            "bao_danh_quan_doan": self.bao_danh_quan_doan.isChecked(),
            "thiet_lap_muu_binh": self.thiet_lap_muu_binh.isChecked(),
        }

    def start_bot(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        config = self._current_config()
        self._worker = BotWorker(
            serial=self._settings.adb_serial,
            screenshot_dir=self._settings.screenshot_dir,
            config=config,
            parent=self,
        )
        self._worker.log_message.connect(self._log)
        self._worker.finished.connect(self._on_worker_finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._log("Đang chạy tác vụ nền…")
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
