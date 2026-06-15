from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from youtube_audio_converter import dependencies
from .models import FORMATS
from .progress_tree import ProgressTree


class LayoutMixin:
    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(18, 12, 18, 12)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QtWidgets.QLabel("YouTube Audio/Video Downloader and Converter")
        title.setObjectName("appTitle")
        self.lbl_badge = QtWidgets.QLabel("READY")
        self.lbl_badge.setObjectName("badgeReady")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.lbl_badge)
        root.addLayout(header)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self._configure_splitter(self.main_splitter)
        self.main_splitter.addWidget(self._build_left_pane())
        self.main_splitter.addWidget(self._build_right_pane())
        self.main_splitter.setSizes([480, 720])
        root.addWidget(self.main_splitter, 1)
        root.addWidget(self._build_bottom_bar())

    def _build_left_pane(self) -> QtWidgets.QWidget:
        pane = QtWidgets.QWidget()
        pane.setMinimumWidth(340)
        layout = QtWidgets.QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self._configure_splitter(self.left_splitter)
        self.left_splitter.addWidget(self._build_playlist_section())
        self.left_splitter.addWidget(self._build_output_section())
        self.left_splitter.addWidget(self._build_settings_section())
        self.left_splitter.setStretchFactor(0, 2)
        self.left_splitter.setStretchFactor(1, 0)
        self.left_splitter.setStretchFactor(2, 3)
        self.left_splitter.setSizes([260, 96, 360])
        layout.addWidget(self.left_splitter, 1)
        return pane

    def _build_right_pane(self) -> QtWidgets.QWidget:
        pane = self._card()
        layout = QtWidgets.QVBoxLayout(pane)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(self._section_label("Run View"))
        header.addStretch(1)
        self.hide_inactive_check = QtWidgets.QCheckBox("Hide inactive tasks")
        self.hide_inactive_check.setChecked(True)
        self.hide_inactive_check.toggled.connect(self._on_hide_inactive_tasks_changed)
        self.suppress_js_check = QtWidgets.QCheckBox("Suppress JS Warn")
        self.suppress_js_check.setChecked(True)
        self.autoscroll_check = QtWidgets.QCheckBox("Auto-scroll")
        self.autoscroll_check.setChecked(True)
        header.addWidget(self.hide_inactive_check)
        header.addWidget(self.suppress_js_check)
        header.addWidget(self.autoscroll_check)
        layout.addLayout(header)

        self.run_tabs = QtWidgets.QTabWidget()
        self._build_progress_page()
        self._build_log_page()
        self.run_tabs.addTab(self.progress_page, "Progress View")
        self.run_tabs.addTab(self.log_page, "Log View")
        layout.addWidget(self.run_tabs, 1)
        return pane

    def _build_progress_page(self):
        self.progress_page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.progress_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.progress_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self._configure_splitter(self.progress_splitter)
        layout.addWidget(self.progress_splitter, 1)

        summary_panel = QtWidgets.QWidget()
        summary_panel.setMinimumHeight(52)
        summary_layout = QtWidgets.QVBoxLayout(summary_panel)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(5)

        summary = QtWidgets.QHBoxLayout()
        self.lbl_current = QtWidgets.QLabel("Idle")
        self.lbl_current.setObjectName("mutedMono")
        self.lbl_progress_count = QtWidgets.QLabel("0 / 0 files")
        self.lbl_progress_count.setObjectName("mutedMono")
        summary.addWidget(self.lbl_current, 1)
        summary.addWidget(self.lbl_progress_count)
        summary_layout.addLayout(summary)

        self.pb_overall = QtWidgets.QProgressBar()
        self.pb_overall.setRange(0, 100)
        self.pb_overall.setValue(0)
        summary_layout.addWidget(self.pb_overall)

        self.progress_tree = ProgressTree()
        self.progress_splitter.addWidget(summary_panel)
        self.progress_splitter.addWidget(self.progress_tree)
        self.progress_splitter.setStretchFactor(0, 0)
        self.progress_splitter.setStretchFactor(1, 1)
        self.progress_splitter.setSizes([62, 620])

    def _build_log_page(self):
        self.log_page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.log_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch(1)
        self.btn_save_log = QtWidgets.QPushButton("Save Log")
        self.btn_save_log.clicked.connect(self._save_log)
        self.btn_clear_log = QtWidgets.QPushButton("Clear Log")
        self.btn_clear_log.clicked.connect(self._clear_logs)
        actions.addWidget(self.btn_save_log)
        actions.addWidget(self.btn_clear_log)
        layout.addLayout(actions)
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(12000)
        layout.addWidget(self.log_text, 1)

    def _build_playlist_section(self) -> QtWidgets.QFrame:
        card = self._card()
        card.setMinimumHeight(110)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self._section_label("Sources"))
        row.addStretch(1)
        for text, callback in (
            ("Add", self._add_playlist_row),
            ("Remove", self._remove_selected_url_rows),
            ("Import", self._import_txt),
            ("Paste", self._paste_urls),
            ("Clear", self._clear_playlist_rows),
        ):
            row.addWidget(self._small_button(text, callback))
        layout.addLayout(row)

        self.url_table = QtWidgets.QTableWidget(0, 1)
        self.url_table.setHorizontalHeaderLabels(["Source URL or Label | URL"])
        self.url_table.horizontalHeader().setStretchLastSection(True)
        self.url_table.verticalHeader().setDefaultSectionSize(31)
        self.url_table.setAlternatingRowColors(False)
        self.url_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.url_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.url_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.url_table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.url_table.setShowGrid(False)
        layout.addWidget(self.url_table, 1)

        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Delete, self.url_table, activated=self._remove_selected_url_rows)
        self._add_playlist_row()
        self._add_playlist_row()
        return card

    def _build_output_section(self) -> QtWidgets.QFrame:
        card = self._card()
        card.setMinimumHeight(76)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self._section_label("Output Folder"))

        row = QtWidgets.QHBoxLayout()
        self.output_dir_edit = QtWidgets.QLineEdit(str(Path.home() / "Music" / "AudioBooks"))
        row.addWidget(self.output_dir_edit, 1)
        row.addWidget(self._small_button("Open", self._open_output_dir))
        row.addWidget(self._small_button("Browse...", self._browse_output))
        layout.addLayout(row)
        return card

    def _build_settings_section(self) -> QtWidgets.QFrame:
        card = self._card()
        card.setMinimumHeight(150)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self._section_label("Settings"))

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        body = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(body)
        form.setContentsMargins(0, 0, 4, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(5)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._add_settings_rows(form)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self._on_format_changed()
        return card

    def _add_settings_rows(self, form: QtWidgets.QFormLayout):
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(list(FORMATS.keys()))
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        form.addRow("Format", self.format_combo)

        self.quality_combo = QtWidgets.QComboBox()
        form.addRow("Quality", self.quality_combo)

        self.speed_combo = QtWidgets.QComboBox()
        self.speed_combo.addItems(["0.5", "0.75", "1.0", "1.1", "1.25", "1.3", "1.5", "1.75", "2.0"])
        self.speed_combo.setCurrentText("1.0")
        form.addRow("Playback Speed", self.speed_combo)

        self.volume_spin = QtWidgets.QDoubleSpinBox()
        self.volume_spin.setRange(0.01, 10.0)
        self.volume_spin.setDecimals(2)
        self.volume_spin.setSingleStep(0.1)
        self.volume_spin.setValue(1.0)
        self.volume_spin.setSuffix("x")
        form.addRow("Volume", self.volume_spin)

        self.concurrent_downloads_spin = QtWidgets.QSpinBox()
        self.concurrent_downloads_spin.setRange(1, 8)
        self.concurrent_downloads_spin.setValue(2)
        form.addRow("Concurrent DLs", self.concurrent_downloads_spin)

        self.concurrent_converts_spin = QtWidgets.QSpinBox()
        self.concurrent_converts_spin.setRange(1, 8)
        self.concurrent_converts_spin.setValue(1)
        form.addRow("Concurrent Converts", self.concurrent_converts_spin)

        self.download_start_delay_spin = QtWidgets.QDoubleSpinBox()
        self.download_start_delay_spin.setRange(0, 60)
        self.download_start_delay_spin.setDecimals(0)
        self.download_start_delay_spin.setSingleStep(1)
        self.download_start_delay_spin.setValue(10)
        self.download_start_delay_spin.setSuffix(" sec")
        form.addRow("DL Start Gap", self.download_start_delay_spin)

        cookie_row = QtWidgets.QHBoxLayout()
        self.cookiefile_edit = QtWidgets.QLineEdit()
        cookie_row.addWidget(self.cookiefile_edit, 1)
        cookie_row.addWidget(self._small_button("Browse...", self._browse_cookies))
        cookie_row.addWidget(self._small_button("Clear", self._clear_cookies))
        form.addRow("Cookies File", cookie_row)

        browser_row = QtWidgets.QHBoxLayout()
        self.browser_combo = QtWidgets.QComboBox()
        self.browser_combo.addItems(["None", "chrome", "chromium", "edge", "firefox", "opera", "safari"])
        browser_row.addWidget(self.browser_combo, 1)
        browser_row.addWidget(self._small_button("Download Deno", self._download_deno))
        form.addRow("Browser Cookies", browser_row)

        self._add_option_checks(form)

    def _add_option_checks(self, form: QtWidgets.QFormLayout):
        option_grid = QtWidgets.QGridLayout()
        self.thumbnail_check = QtWidgets.QCheckBox("Embed Thumbnail")
        self.thumbnail_check.setChecked(True)
        self.crop_thumb_check = QtWidgets.QCheckBox("Crop to Square")
        self.crop_thumb_check.setChecked(True)
        self.metadata_check = QtWidgets.QCheckBox("Embed Metadata")
        self.metadata_check.setChecked(True)
        self.track_num_check = QtWidgets.QCheckBox("Number Tracks")
        self.track_num_check.setChecked(True)
        self.skip_existing_check = QtWidgets.QCheckBox("Skip Existing")
        self.skip_existing_check.setChecked(True)
        self.use_deno_check = QtWidgets.QCheckBox("Use Deno")
        self.use_deno_check.setEnabled(bool(dependencies.get_deno_path()))
        for index, widget in enumerate(
            [
                self.thumbnail_check,
                self.crop_thumb_check,
                self.metadata_check,
                self.track_num_check,
                self.skip_existing_check,
                self.use_deno_check,
            ]
        ):
            option_grid.addWidget(widget, index // 2, index % 2)
        form.addRow("", option_grid)

    def _build_bottom_bar(self) -> QtWidgets.QFrame:
        bar = QtWidgets.QFrame()
        bar.setObjectName("bottomBar")
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn_start = self._bottom_button("Start Download", "primaryButton", self._start)
        self.btn_stop = self._bottom_button("Stop", "dangerButton", self._stop)
        self.btn_stop.setEnabled(False)
        self.btn_retry = self._bottom_button("Retry Errors", "", self._retry_errors)
        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.btn_retry)
        layout.addSpacing(14)
        layout.addWidget(QtWidgets.QLabel("When done:"))
        self.when_done_combo = QtWidgets.QComboBox()
        self.when_done_combo.addItems(["Do nothing", "Sleep", "Hibernate", "Shutdown", "Reboot", "Logoff"])
        layout.addWidget(self.when_done_combo)
        layout.addStretch(1)

        made_by = QtWidgets.QLabel("made by ad1107")
        made_by.setObjectName("mutedMono")
        self.lbl_dep_status = QtWidgets.QLabel("")
        self.lbl_dep_status.setObjectName("mutedMono")
        layout.addWidget(made_by)
        layout.addWidget(self.lbl_dep_status)
        return bar

    def _bottom_button(self, text: str, object_name: str, callback) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        if object_name:
            button.setObjectName(object_name)
        button.setFixedSize(124, 34)
        button.clicked.connect(callback)
        return button

    def _card(self) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("card")
        return frame

    def _section_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _small_button(self, text: str, callback) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setMinimumHeight(28)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _configure_splitter(self, splitter: QtWidgets.QSplitter):
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.setOpaqueResize(True)
