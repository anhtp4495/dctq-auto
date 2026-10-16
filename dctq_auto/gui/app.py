"""GUI application bootstrap."""

import sys

from PySide6.QtWidgets import QApplication

from dctq_auto.gui.main_window import MainWindow


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DCTQ Auto")
    window = MainWindow()
    window.show()
    return app.exec()
