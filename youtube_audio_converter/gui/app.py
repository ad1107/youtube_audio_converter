import sys

from PySide6 import QtWidgets

from .styles import app_palette, app_stylesheet
from .window import MainWindow


class YoutubeAudioConverter(QtWidgets.QApplication):
    def __init__(self):
        super().__init__(sys.argv[:1])
        self.setApplicationName("YouTube Audio/Video Converter")
        self.setOrganizationName("youtube_audio_converter")
        self.setStyle("Fusion")
        self.setPalette(app_palette())
        self.setStyleSheet(app_stylesheet())
        self.main_window = MainWindow()

    def show(self):
        self.main_window.show()

    def mainloop(self) -> int:
        if not self.main_window.isVisible():
            self.main_window.show()
        return self.exec()
