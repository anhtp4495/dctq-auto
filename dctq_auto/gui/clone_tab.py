"""Giao diện cấu hình chạy lần lượt các tài khoản clone."""

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dctq_auto.tasks.clone.accounts import load_accounts


class CloneTab(QWidget):
    """Chọn file tài khoản và các nhiệm vụ cần thực hiện cho mỗi tài khoản."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Chạy các nhiệm vụ đã chọn lần lượt trên từng tài khoản trong file TXT. "
            "Mỗi dòng dùng định dạng username|password."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        file_row = QHBoxLayout()
        self.account_file_input = QLineEdit()
        self.account_file_input.setPlaceholderText("Chọn file tài khoản .txt")
        self.account_file_input.setClearButtonEnabled(True)
        self.account_file_input.textChanged.connect(self._update_account_status)
        file_row.addWidget(self.account_file_input, 1)
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

        self.clone_login = QCheckBox("Đăng nhập")
        self.clone_login.setChecked(True)
        self.clone_daily_check_in = QCheckBox("Điểm danh")
        self.clone_daily_check_in.setChecked(True)
        self.clone_guild_check_in = QCheckBox("Báo danh quân đoàn")
        self.clone_guild_check_in.setChecked(True)
        self.clone_receive_lucky_bag = QCheckBox("Nhận túi phúc")
        self.clone_receive_lucky_bag.setChecked(True)
        self.clone_logout = QCheckBox("Đăng xuất")
        self.clone_logout.setChecked(True)

        for checkbox in (
            self.clone_login,
            self.clone_daily_check_in,
            self.clone_guild_check_in,
            self.clone_receive_lucky_bag,
            self.clone_logout,
        ):
            layout.addWidget(checkbox)

        note = QLabel(
            "Lưu ý: file TXT chứa mật khẩu dạng văn bản thuần; hãy giữ file ở nơi an toàn. "
            "Phần giao diện và đọc danh sách đã có; thao tác đăng nhập/điểm danh trong game "
            "cần được nối với logic điều khiển ADB/OCR trước khi chạy thật."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #B45309;")
        layout.addWidget(note)
        layout.addStretch(1)

    def _browse_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn danh sách tài khoản",
            str(Path.home()),
            "Text files (*.txt);;All files (*)",
        )
        if filename:
            self.account_file_input.setText(filename)

    def _update_account_status(self, *_args) -> None:
        filename = self.account_file_input.text().strip()
        if not filename:
            self.account_status.setText("Chưa chọn file tài khoản.")
            return
        try:
            accounts = load_accounts(filename)
        except FileNotFoundError:
            self.account_status.setText("Chưa tìm thấy file. Hãy kiểm tra đường dẫn.")
        except (OSError, UnicodeError, ValueError) as exc:
            self.account_status.setText(f"Danh sách chưa hợp lệ: {exc}")
        else:
            self.account_status.setText(f"Đã đọc {len(accounts)} tài khoản hợp lệ.")

    def current_config(self) -> dict:
        """Lấy cấu hình clone; không đưa mật khẩu vào cấu hình hoặc nhật ký."""
        return {
            "clone_mode": True,
            "clone_account_file": self.account_file_input.text().strip(),
            "clone_login": self.clone_login.isChecked(),
            "clone_daily_check_in": self.clone_daily_check_in.isChecked(),
            "clone_guild_check_in": self.clone_guild_check_in.isChecked(),
            "clone_receive_lucky_bag": self.clone_receive_lucky_bag.isChecked(),
            "clone_logout": self.clone_logout.isChecked(),
        }
