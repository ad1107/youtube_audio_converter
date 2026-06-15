from __future__ import annotations

import threading
from datetime import datetime

from PySide6 import QtCore, QtWidgets

from youtube_audio_converter import __version__, dependencies
from youtube_audio_converter.core.download_types import PlaylistJob
from youtube_audio_converter.core.runtime import DownloadRuntime

from .controls import ControlsMixin
from .dependency_dialog import QtDependencyProgress
from .download_controller import DownloadControllerMixin
from .layout import LayoutMixin
from .log_view import LogViewMixin
from .power import GUIPowerMixin
from .progress_events import ProgressEventsMixin
from .signals import GuiSignals


class MainWindow(
    QtWidgets.QMainWindow,
    LayoutMixin,
    ControlsMixin,
    LogViewMixin,
    ProgressEventsMixin,
    DownloadControllerMixin,
    GUIPowerMixin,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"YouTube Audio/Video Downloader and Converter v{__version__}")
        self.setMinimumSize(1180, 720)
        self.jobs: list[PlaylistJob] = []
        self.failed_items: list[dict] = []
        self.failed_items_lock = threading.Lock()
        self.is_running = False
        self.cancel_flag = threading.Event()
        self.download_runtime: DownloadRuntime | None = None
        self.run_config: dict = {}
        self._last_item_emit: dict[str, tuple[float, float | None, str]] = {}
        self._item_emit_lock = threading.Lock()
        self._setup_signals()
        self._build_ui()
        self._check_dependencies()
        self._write_startup_log()

    def _setup_signals(self):
        self.signals = GuiSignals(self)
        self.signals.log_entry.connect(self._queue_log_entry)
        self.signals.current_text.connect(self.lbl_current_set_text)
        self.signals.overall_state.connect(self._queue_overall_state)
        self.signals.job_state.connect(self._queue_job_state)
        self.signals.item_state.connect(self._queue_item_state)
        self.signals.all_finished.connect(self._on_all_finished)

        self.pending_logs: list[tuple[str, str, str, datetime]] = []
        self.pending_jobs: dict[int, dict] = {}
        self.pending_items: dict[str, dict] = {}
        self.pending_overall: tuple[float, str] | None = None
        self.flush_timer = QtCore.QTimer(self)
        self.flush_timer.setInterval(80)
        self.flush_timer.setSingleShot(True)
        self.flush_timer.timeout.connect(self._flush_ui_updates)

    def _write_startup_log(self):
        self.log("SYSTEM", "YouTube Audio/Video Downloader and Converter", "SYSTEM")
        self.log("SYSTEM", "Supported audio: M4A, HE-AAC, MP3, Opus, FLAC, WAV, AIFF, ALAC", "INFO")
        self.log("SYSTEM", "Supported video: MP4, MKV, WebM", "INFO")
        self.log("SYSTEM", "Tip: Add playlist or single-video URLs; type is auto-detected", "INFO")
        if not dependencies.get_ffmpeg_path():
            self.log("SYSTEM", "Missing: ffmpeg", "WARNING")
            self.log("SYSTEM", "https://ffmpeg.org", "WARNING")

    def create_progress_reporter(self, title: str, heading: str):
        return QtDependencyProgress(self, title, heading)

    def refresh_dependencies(self):
        self._check_dependencies()

    def log(self, source: str, message: str, level: str = "INFO"):
        self.signals.log_entry.emit(str(source or ""), str(message), str(level or "INFO"), datetime.now())

    def lbl_current_set_text(self, text: str):
        self.lbl_current.setText(text)

    def _queue_log_entry(self, source: str, message: str, level: str, ts: datetime):
        self.pending_logs.append((source, message, level, ts))
        self._schedule_flush()

    def _queue_overall_state(self, value: float, label: str):
        self.pending_overall = (value, label)
        self._schedule_flush()

    def _queue_job_state(self, job_id: int, state: dict):
        self.pending_jobs[job_id] = dict(state)
        self._schedule_flush()

    def _queue_item_state(self, key: str, state: dict):
        self.pending_items[key] = dict(state)
        self._schedule_flush()

    def _schedule_flush(self):
        if not self.flush_timer.isActive():
            self.flush_timer.start()

    def _flush_ui_updates(self):
        if self.pending_logs:
            entries = self.pending_logs
            self.pending_logs = []
            self._write_log_batch(entries)

        if self.pending_overall:
            value, label = self.pending_overall
            self.pending_overall = None
            self.pb_overall.setValue(int(max(0, min(100, value))))
            self.lbl_progress_count.setText(label)

        if self.pending_jobs:
            jobs = self.pending_jobs
            self.pending_jobs = {}
            for job_id, state in sorted(jobs.items()):
                self.progress_tree.apply_job_state(job_id, state)

        if self.pending_items:
            items = self.pending_items
            self.pending_items = {}
            for key in sorted(items, key=self._progress_sort_key):
                self.progress_tree.apply_item_state(key, items[key])

    def _refresh_badge_style(self):
        self.lbl_badge.style().unpolish(self.lbl_badge)
        self.lbl_badge.style().polish(self.lbl_badge)

    def closeEvent(self, event):
        if self.is_running:
            result = QtWidgets.QMessageBox.question(
                self,
                "Downloads Running",
                "Downloads are still running. Stop and close?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if result != QtWidgets.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.cancel_flag.set()
        self._set_system_sleep_state(prevent=False)
        event.accept()
