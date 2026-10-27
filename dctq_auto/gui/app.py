"""GUI application bootstrap."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from dctq_auto.gui.main_window import MainWindow
from dctq_auto.gui.license_dialog import LicenseDialog
from dctq_auto.licensing import read_license


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DCTQ Auto")

    valid, message, _ = read_license()
    if not valid:
        activation = LicenseDialog()
        if activation.exec() != LicenseDialog.DialogCode.Accepted:
            return 0
        valid, message, _ = read_license()
        if not valid:
            QMessageBox.critical(None, "License không hợp lệ", message)
            return 1

    window = MainWindow()
    window.show()
    return app.exec()
