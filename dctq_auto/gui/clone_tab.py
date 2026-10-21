"""Giao diện cấu hình chạy lần lượt các tài khoản clone."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.tasks.common.accounts import load_accounts


class CloneTab(QWidget):
    """Chọn file tài khoản và các nhiệm vụ cần thực hiện cho mỗi tài khoản."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        intro = QLabel(
            "Chạy các nhiệm vụ đã chọn lần lượt trên từng tài khoản trong file TXT. "
            "Mỗi dòng dùng định dạng username|password."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        file_row = QHBoxLayout()
        self.account_file_combo = QComboBox()
        self.account_file_combo.setMinimumContentsLength(12)
        self.account_file_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.account_file_combo.setToolTip("Chọn file tài khoản đã dùng trước đây")
        self.account_file_combo.currentIndexChanged.connect(self._update_account_status)
        self.account_file_combo.currentIndexChanged.connect(self._show_selected_file_path)
        self.account_file_combo.activated.connect(self._show_selected_file_path)
        file_row.addWidget(self.account_file_combo, 1)
        self.browse_button = QPushButton("Chọn file…")
        self.browse_button.clicked.connect(self._browse_file)
        file_row.addWidget(self.browse_button)
        layout.addLayout(file_row)

        self.account_status = QLabel("Chưa chọn file tài khoản.")
        self.account_status.setWordWrap(True)
        layout.addWidget(self.account_status)

        tasks_label = QLabel("Nhiệm vụ cho mỗi tài khoản")
        tasks_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(tasks_label)

        phuc_loi_group = QGroupBox("Hoạt động - Phúc lợi")
        phuc_loi_layout = QVBoxLayout(phuc_loi_group)
        self.clone_daily_check_in = QCheckBox("Điểm danh")
        self.clone_daily_check_in.setChecked(True)
        self.clone_receive_quoc_van = QCheckBox("Nhận lễ bao quốc vận")
        self.clone_receive_quoc_van.setChecked(False)
        phuc_loi_layout.addWidget(self.clone_receive_quoc_van)
        phuc_loi_layout.addWidget(self.clone_daily_check_in)
        layout.addWidget(phuc_loi_group)

        guild_group = QGroupBox("Quân đoàn")
        guild_layout = QVBoxLayout(guild_group)
        self.clone_guild_check_in = QCheckBox("Báo danh quân đoàn")
        self.clone_guild_check_in.setChecked(True)
        self.clone_receive_lucky_bag = QCheckBox("Nhận túi phúc")
        self.clone_receive_lucky_bag.setChecked(True)
        self.clone_guild_fortune = QCheckBox("Cầu vận quân đoàn (5 lần)")
        for checkbox in (
            self.clone_guild_check_in,
            self.clone_receive_lucky_bag,
            self.clone_guild_fortune,
        ):
            guild_layout.addWidget(checkbox)
        layout.addWidget(guild_group)

        self.clone_quoc_chien = QCheckBox("Quốc chiến")
        layout.addWidget(self.clone_quoc_chien)

        layout.addStretch(1)
        scroll_area.setWidget(page)
        outer_layout.addWidget(scroll_area)

    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn danh sách tài khoản",
            str(Path.home()),
            "Text files (*.txt);;All files (*)",
        )
        if filename:
            self.add_account_file(filename)

    def add_account_file(self, filename: str) -> None:
        """Add a selected account file to the dropdown, keeping paths unique."""
        filename = str(Path(filename).expanduser().resolve())
        index = self.account_file_combo.findData(filename)
        if index < 0:
            self.account_file_combo.addItem(Path(filename).name, filename)
            index = self.account_file_combo.count() - 1
        self.account_file_combo.setCurrentIndex(index)

    def set_account_files(self, filenames: list[str], selected: str = "") -> None:
        """Restore previously used file paths from application settings."""
        self.account_file_combo.blockSignals(True)
        self.account_file_combo.clear()
        seen = set()
        for filename in filenames:
            if not filename:
                continue
            path = str(Path(filename).expanduser())
            if path not in seen:
                self.account_file_combo.addItem(Path(path).name, path)
                seen.add(path)
        if selected:
            path = str(Path(selected).expanduser())
            index = self.account_file_combo.findData(path)
            if index < 0:
                self.account_file_combo.addItem(path, path)
                index = self.account_file_combo.count() - 1
            self.account_file_combo.setCurrentIndex(index)
        elif self.account_file_combo.count():
            self.account_file_combo.setCurrentIndex(0)
        self.account_file_combo.blockSignals(False)
        self._update_account_status()

    def _show_selected_file_path(self, *_args) -> None:
        filename = self.account_file()

    def account_file(self) -> str:
        value = self.account_file_combo.currentData()
        return str(value or self.account_file_combo.currentText()).strip()

    def account_files(self) -> list[str]:
        return [
            str(self.account_file_combo.itemData(index) or self.account_file_combo.itemText(index))
            for index in range(self.account_file_combo.count())
        ]

    def _update_account_status(self, *_args) -> None:
        filename = self.account_file()
        if not filename:
            self.account_status.setText("Chưa chọn file tài khoản.")
            return
        try:
            accounts = load_accounts(filename)
        except FileNotFoundError:
            self.account_status.setText("Chưa tìm thấy file. Hãy kiểm tra đường dẫn.")
        except (OSError, UnicodeError, ValueError) as exc:
            self.account_status.setText(str(exc))
        else:
            self.account_status.setText(f"Đã đọc {len(accounts)} tài khoản hợp lệ.")

    def current_config(self) -> dict:
        """Lấy cấu hình clone; không đưa mật khẩu vào cấu hình hoặc nhật ký."""
        return {
            "clone_mode": True,
            "clone_account_file": self.account_file(),
            "clone_login": True,
            "clone_daily_check_in": self.clone_daily_check_in.isChecked(),
            "clone_receive_quoc_van": self.clone_receive_quoc_van.isChecked(),
            "clone_guild_check_in": self.clone_guild_check_in.isChecked(),
            "clone_receive_lucky_bag": self.clone_receive_lucky_bag.isChecked(),
            "clone_guild_fortune": self.clone_guild_fortune.isChecked(),
            "clone_quoc_chien": self.clone_quoc_chien.isChecked(),
            "clone_logout": True,
        }
