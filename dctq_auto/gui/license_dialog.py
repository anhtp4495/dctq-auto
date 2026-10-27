"""First-run activation dialog for offline licenses."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)

from dctq_auto.licensing import device_id, license_path, validate_license


class LicenseDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kích hoạt License - DCTQ Auto")
        self.setModal(True)
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        title = QLabel("Kích hoạt DCTQ Auto")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel(
            "Ứng dụng cần License hợp lệ để tiếp tục. License được xác minh offline "
            "và chỉ dùng được trên máy tính được cấp."
        ))
        layout.addWidget(QLabel("Mã thiết bị của máy này:"))
        self.device_label = QLabel(device_id())
        self.device_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.device_label.setWordWrap(True)
        self.device_label.setStyleSheet("font-family: monospace; padding: 8px; border: 1px solid #888;")
        layout.addWidget(self.device_label)
        layout.addWidget(QLabel(
            "Gửi mã thiết bị cho người cấp License. Sau khi nhận file .lic, "
            "chọn file đó để kích hoạt."
        ))
        buttons = QHBoxLayout()
        copy_button = QPushButton("Sao chép mã thiết bị")
        copy_button.clicked.connect(self._copy_device_id)
        buttons.addWidget(copy_button)
        activate_button = QPushButton("Chọn file License…")
        activate_button.clicked.connect(self._select_license)
        buttons.addWidget(activate_button)
        layout.addLayout(buttons)
        exit_button = QPushButton("Thoát")
        exit_button.clicked.connect(self.reject)
        layout.addWidget(exit_button)

    def _copy_device_id(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(device_id())
        QMessageBox.information(self, "Đã sao chép", "Đã sao chép mã thiết bị.")

    def _select_license(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Chọn file License", "", "License (*.lic *.json);;Tất cả tệp (*.*)"
        )
        if not filename:
            return
        source = Path(filename)
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            QMessageBox.warning(self, "License không hợp lệ", "Không đọc được file License.")
            return
        if not isinstance(document, dict):
            QMessageBox.warning(self, "License không hợp lệ", "Cấu trúc file License không đúng.")
            return
        valid, message = validate_license(document)
        if not valid:
            QMessageBox.warning(self, "Không thể kích hoạt", message)
            return
        target = license_path()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        except OSError as exc:
            QMessageBox.critical(self, "Lỗi lưu License", f"Không lưu được License: {exc}")
            return
        QMessageBox.information(self, "Kích hoạt thành công", message)
        self.accept()
