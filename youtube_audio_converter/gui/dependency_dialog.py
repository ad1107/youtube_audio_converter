import time

from PySide6 import QtCore, QtWidgets


class QtDependencyProgress:
    def __init__(self, parent, title: str, heading: str):
        self.dialog = QtWidgets.QDialog(parent)
        self.dialog.setWindowTitle(title)
        self.dialog.setModal(True)
        self.dialog.setMinimumWidth(420)
        self.dialog.setWindowFlag(QtCore.Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self.dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        label = QtWidgets.QLabel(heading)
        label.setObjectName("dialogHeading")
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.status = QtWidgets.QLabel("Starting download...")
        self.status.setObjectName("muted")
        layout.addWidget(label)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self.start_time = time.time()
        self.dialog.show()
        QtWidgets.QApplication.processEvents()

    def set_status(self, text: str) -> None:
        self.status.setText(text)
        QtWidgets.QApplication.processEvents()

    def reporthook(self, blocknum, blocksize, totalsize) -> None:
        if blocknum == 0:
            self.start_time = time.time()
            return

        elapsed = max(time.time() - self.start_time, 0.001)
        current = blocknum * blocksize
        if totalsize > 0:
            percent = min(current * 100.0 / totalsize, 100)
            self.progress.setRange(0, 100)
            self.progress.setValue(int(percent))
            total_mb = totalsize / (1024 * 1024)
        else:
            percent = 0
            self.progress.setRange(0, 0)
            total_mb = 0
        downloaded_mb = current / (1024 * 1024)
        speed = current / elapsed
        speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.1f} KB/s"
        if totalsize > 0:
            self.status.setText(f"{percent:.0f}% | {downloaded_mb:.1f}/{total_mb:.1f} MB | {speed_text}")
        else:
            self.status.setText(f"{downloaded_mb:.1f} MB | {speed_text}")
        QtWidgets.QApplication.processEvents()

    def close(self) -> None:
        self.dialog.accept()
        QtWidgets.QApplication.processEvents()

    def show_error(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.critical(self.dialog, title, message)
        self.dialog.reject()
        QtWidgets.QApplication.processEvents()
