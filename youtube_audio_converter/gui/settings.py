import tkinter as tk
from tkinter import ttk

from youtube_audio_converter import dependencies
from .models import FORMATS, QUALITIES, Theme


class GUISettingsMixin:
    def _build_settings_section(self, parent):
        card = self._card(parent, margin_bottom=10)
        hrow = tk.Frame(card, bg=Theme.BG2, padx=12, pady=10)
        hrow.pack(fill="x")
        self._section_label(hrow, "SETTINGS").pack(anchor="w")

        body = tk.Frame(card, bg=Theme.BG2, padx=12)
        body.pack(fill="x", pady=(0, 8))
        label_width = 15

        self._format_quality_rows(body, label_width)
        self._audio_adjustment_rows(body, label_width)
        self._concurrency_rows(body, label_width)
        self._cookie_rows(body, label_width)
        self._option_checkboxes(body)

    def _format_quality_rows(self, parent, label_width: int):
        row = self._settings_row(parent, "Format", label_width)
        ttk.Combobox(
            row,
            textvariable=self.var_format,
            values=list(FORMATS.keys()),
            state="readonly",
            font=("Helvetica Neue", 10),
            width=30,
        ).pack(side="left")

        row = self._settings_row(parent, "Quality", label_width)
        self.cb_quality = ttk.Combobox(
            row,
            textvariable=self.var_quality,
            values=list(QUALITIES.keys()),
            state="readonly",
            font=("Helvetica Neue", 10),
            width=22,
        )
        self.cb_quality.pack(side="left")

        def on_format_change(*args):
            fmt_code = FORMATS.get(self.var_format.get(), "m4a")
            self.cb_quality.config(state="disabled" if fmt_code in ["flac", "wav", "alac", "aiff"] else "readonly")

        self.var_format.trace_add("write", on_format_change)
        on_format_change()

    def _audio_adjustment_rows(self, parent, label_width: int):
        row = self._settings_row(parent, "Playback Speed", label_width)
        ttk.Combobox(
            row,
            textvariable=self.var_speed,
            values=[0.5, 0.75, 1.0, 1.1, 1.25, 1.3, 1.5, 1.75, 2.0],
            state="readonly",
            font=("Helvetica Neue", 10),
            width=8,
        ).pack(side="left")
        self._muted_note(row, "x (Retains pitch, 1.0=Normal)")

        row = self._settings_row(parent, "Volume", label_width)
        tk.Entry(
            row,
            textvariable=self.var_volume,
            bg=Theme.BG3,
            fg=Theme.TEXT,
            relief="flat",
            bd=0,
            font=("Courier New", 10),
            insertbackground=Theme.TEXT,
            width=8,
        ).pack(side="left", ipady=4)
        self._muted_note(row, "x (FFmpeg volume filter)")

    def _concurrency_rows(self, parent, label_width: int):
        row = self._settings_row(parent, "Concurrent DLs", label_width)
        self._spinbox(row, self.var_concurrent_downloads, 1, 8)
        self._muted_note(row, "(tracks at once)")

        row = self._settings_row(parent, "Concurrent Converts", label_width)
        self._spinbox(row, self.var_concurrent_converts, 1, 8)

        row = self._settings_row(parent, "DL Start Gap", label_width)
        self._spinbox(row, self.var_download_start_delay, 0, 60, increment=1)
        self._muted_note(row, "seconds between new downloads")

    def _cookie_rows(self, parent, label_width: int):
        row = self._settings_row(parent, "Cookies File", label_width)
        tk.Entry(
            row,
            textvariable=self.var_cookiefile,
            bg=Theme.BG3,
            fg=Theme.TEXT,
            relief="flat",
            bd=0,
            font=("Courier New", 9),
            insertbackground=Theme.TEXT,
        ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self._small_btn(row, "Clear", self._clear_cookies).pack(side="right", padx=(4, 0))
        self._small_btn(row, "Browse...", self._browse_cookies).pack(side="right")

        row = self._settings_row(parent, "Browser Cookies", label_width)
        ttk.Combobox(
            row,
            textvariable=self.var_cookies_browser,
            values=["None", "chrome", "chromium", "edge", "firefox", "opera", "safari"],
            state="readonly",
            font=("Helvetica Neue", 10),
            width=14,
        ).pack(side="left")
        self._small_btn(row, "Download Deno", self._download_deno).pack(side="right", padx=(4, 0))

    def _option_checkboxes(self, parent):
        frame = tk.Frame(parent, bg=Theme.BG2)
        frame.pack(fill="x", pady=(8, 0))
        options = [
            ("Embed Thumbnail", self.var_thumbnail),
            ("Crop to Square", self.var_crop_thumb),
            ("Embed Metadata", self.var_metadata),
            ("Number Tracks", self.var_track_num),
            ("Skip Existing", self.var_skip_existing),
        ]
        for i, (label, var) in enumerate(options):
            tk.Checkbutton(
                frame,
                text=label,
                variable=var,
                bg=Theme.BG2,
                fg=Theme.TEXT,
                selectcolor=Theme.BG3,
                activebackground=Theme.BG2,
                activeforeground=Theme.TEXT,
                font=("Helvetica Neue", 10),
                bd=0,
                cursor="hand2",
                highlightthickness=0,
            ).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 12), pady=1)

        deno_state = "normal" if dependencies.get_deno_path() else "disabled"
        if deno_state == "disabled":
            self.var_use_deno.set(False)
        self.chk_use_deno = tk.Checkbutton(
            frame,
            text="Use Deno",
            variable=self.var_use_deno,
            bg=Theme.BG2,
            fg=Theme.TEXT,
            state=deno_state,
            selectcolor=Theme.BG3,
            activebackground=Theme.BG2,
            activeforeground=Theme.TEXT,
            font=("Helvetica Neue", 10),
            bd=0,
            cursor="hand2",
            highlightthickness=0,
        )
        self.chk_use_deno.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=1)

    def _download_deno(self):
        if dependencies.download_deno_if_needed(self):
            if hasattr(self, "chk_use_deno"):
                self.chk_use_deno.config(state="normal")
            if hasattr(self, "_check_dependencies"):
                self._check_dependencies()

    def _settings_row(self, parent, label: str, label_width: int):
        row = tk.Frame(parent, bg=Theme.BG2)
        row.pack(fill="x", pady=3)
        tk.Label(
            row,
            text=label,
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Helvetica Neue", 10),
            width=label_width,
            anchor="w",
        ).pack(side="left")
        return row

    def _spinbox(self, parent, variable, from_, to, increment=1):
        tk.Spinbox(
            parent,
            textvariable=variable,
            from_=from_,
            to=to,
            increment=increment,
            width=4,
            bg=Theme.BG3,
            fg=Theme.TEXT,
            relief="flat",
            bd=0,
            font=("Courier New", 10),
            insertbackground=Theme.TEXT,
            buttonbackground=Theme.BG4,
        ).pack(side="left")

    def _muted_note(self, parent, text: str):
        tk.Label(parent, text=text, bg=Theme.BG2, fg=Theme.MUTED, font=("Helvetica Neue", 9)).pack(side="left", padx=(6, 0))
