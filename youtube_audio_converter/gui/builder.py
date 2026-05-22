import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .models import LOG_COLOURS, Theme


class GUIBuilderMixin:
    def _apply_ttk_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            ".",
            background=Theme.BG2,
            foreground=Theme.TEXT,
            troughcolor=Theme.BG3,
            selectbackground=Theme.ACCENT,
            selectforeground=Theme.BG,
            fieldbackground=Theme.BG3,
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "TCombobox",
            fieldbackground=Theme.BG3,
            foreground=Theme.TEXT,
            background=Theme.BG3,
            selectbackground=Theme.BG3,
            selectforeground=Theme.TEXT,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Theme.BG3)],
            foreground=[("readonly", Theme.TEXT)],
        )
        style.configure("Horizontal.TProgressbar", background=Theme.ACCENT, troughcolor=Theme.BG3, borderwidth=0, thickness=6)
        style.configure("Download.Horizontal.TProgressbar", background=Theme.ACCENT, troughcolor=Theme.BG3, borderwidth=0, thickness=6)
        style.configure("Convert.Horizontal.TProgressbar", background=Theme.PURPLE, troughcolor=Theme.BG3, borderwidth=0, thickness=6)
        style.configure("Green.Horizontal.TProgressbar", background=Theme.GREEN, troughcolor=Theme.BG3, borderwidth=0, thickness=6)
        style.configure("Error.Horizontal.TProgressbar", background=Theme.RED, troughcolor=Theme.BG3, borderwidth=0, thickness=6)
        style.configure("TScrollbar", background=Theme.BG3, troughcolor=Theme.BG2, arrowcolor=Theme.MUTED, borderwidth=0, width=8)

    def _build_ui(self):
        header = tk.Frame(self, bg=Theme.BG, pady=14)
        header.pack(fill="x", padx=24)
        tk.Label(
            header,
            text="YouTube Audio/Video Downloader and Converter",
            bg=Theme.BG,
            fg=Theme.ACCENT,
            font=("Helvetica Neue", 22, "bold"),
        ).pack(side="left")
        self.lbl_badge = tk.Label(header, text="READY", bg=Theme.BG, fg=Theme.GREEN, font=("Courier New", 10, "bold"))
        self.lbl_badge.pack(side="right")
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")

        body = tk.Frame(self, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=24, pady=16)
        body.grid_columnconfigure(0, minsize=500, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=Theme.BG, width=500)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        url_area = tk.Frame(left, bg=Theme.BG)
        url_area.grid(row=0, column=0, sticky="nsew")
        bottom_area = tk.Frame(left, bg=Theme.BG, height=500)
        bottom_area.grid(row=1, column=0, sticky="ew")
        bottom_area.grid_propagate(False)
        bottom_area.pack_propagate(False)
        self._build_playlist_section(url_area, expand=True)
        self._build_output_section(bottom_area)
        self._build_settings_section(bottom_area)

        right = tk.Frame(body, bg=Theme.BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._build_run_view_section(right)

        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")
        self._build_bottom_bar()

    def _build_playlist_section(self, parent, expand=False):
        card = self._card(parent, margin_bottom=10, fill="both" if expand else "x", expand=expand)
        header = tk.Frame(card, bg=Theme.BG2)
        header.pack(fill="x", padx=12, pady=(10, 6))
        self._section_label(header, "URLS").pack(side="left")
        self._small_btn(header, "+ Add Row", self._add_playlist_row).pack(side="right", padx=(4, 0))
        self._small_btn(header, "Import TXT", self._import_txt).pack(side="right", padx=(4, 0))
        self._small_btn(header, "Paste URLs", self._paste_urls).pack(side="right", padx=(4, 0))
        self._small_btn(header, "Clear All", self._clear_playlist_rows).pack(side="right", padx=(4, 0))

        list_outer = tk.Frame(card, bg=Theme.BG2)
        list_outer.pack(fill="both" if expand else "x", expand=expand, padx=12, pady=(0, 10))

        self.playlist_canvas = tk.Canvas(list_outer, bg=Theme.BG2, highlightthickness=0, bd=0, height=170)
        scrollbar = ttk.Scrollbar(list_outer, orient="vertical", command=self.playlist_canvas.yview)
        self.playlist_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.playlist_canvas.pack(side="left", fill="both", expand=True)

        self.playlist_inner = tk.Frame(self.playlist_canvas, bg=Theme.BG2)
        self.canvas_window = self.playlist_canvas.create_window((0, 0), window=self.playlist_inner, anchor="nw")
        self.playlist_inner.bind("<Configure>", self._on_inner_configure)
        self.playlist_canvas.bind("<Configure>", self._on_canvas_configure)

        self._add_playlist_row()
        self._add_playlist_row()

    def _on_inner_configure(self, event):
        self.playlist_canvas.configure(scrollregion=self.playlist_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.playlist_canvas.itemconfig(self.canvas_window, width=event.width)

    def _add_playlist_row(self, url_text=""):
        row = tk.Frame(self.playlist_inner, bg=Theme.BG2)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=f"{len(self.playlist_row_widgets) + 1:02d}", bg=Theme.BG2, fg=Theme.MUTED, font=("Courier New", 9), width=3).pack(side="left", padx=(0, 4))
        entry = tk.Entry(row, bg=Theme.BG3, fg=Theme.TEXT, relief="flat", bd=0, font=("Courier New", 9), insertbackground=Theme.TEXT)
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        if url_text:
            entry.insert(0, url_text)

        def remove(target=row):
            self.playlist_row_widgets = [(frame, ent) for frame, ent in self.playlist_row_widgets if frame is not target]
            target.destroy()
            self._renumber_rows()

        tk.Button(
            row,
            text="X",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Helvetica Neue", 9, "bold"),
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            command=remove,
            activebackground=Theme.BG2,
            activeforeground=Theme.RED,
        ).pack(side="right", padx=(4, 0))
        self.playlist_row_widgets.append((row, entry))

    def _renumber_rows(self):
        for index, (row, _) in enumerate(self.playlist_row_widgets):
            children = row.winfo_children()
            if children:
                children[0].config(text=f"{index + 1:02d}")

    def _import_txt(self):
        filename = filedialog.askopenfilename(title="Select Source TXT File", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if not filename:
            return

        try:
            with open(filename, "r", encoding="utf-8-sig") as file:
                text = file.read()
            self._add_lines_to_rows(text)
        except Exception as exc:
            messagebox.showerror("Read Error", f"Failed to read file: {exc}")

    def _paste_urls(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self._add_lines_to_rows(text)

    def _add_lines_to_rows(self, text: str):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return
        empty_entries = [entry for _, entry in self.playlist_row_widgets if not entry.get().strip()]
        for index, line in enumerate(lines):
            if index < len(empty_entries):
                empty_entries[index].delete(0, "end")
                empty_entries[index].insert(0, line)
            else:
                self._add_playlist_row(url_text=line)

    def _clear_playlist_rows(self):
        for row, _ in self.playlist_row_widgets:
            row.destroy()
        self.playlist_row_widgets.clear()
        self._add_playlist_row()
        self._add_playlist_row()

    def _build_output_section(self, parent):
        card = self._card(parent, margin_bottom=10)
        header = tk.Frame(card, bg=Theme.BG2, padx=12, pady=8)
        header.pack(fill="x")
        self._section_label(header, "OUTPUT FOLDER").pack(anchor="w")

        row = tk.Frame(card, bg=Theme.BG2, padx=12)
        row.pack(fill="x", pady=(0, 10))
        tk.Entry(row, textvariable=self.var_output_dir, bg=Theme.BG3, fg=Theme.TEXT, relief="flat", bd=0, font=("Courier New", 9), insertbackground=Theme.TEXT).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self._small_btn(row, "Open", self._open_output_dir).pack(side="right", padx=(0, 4))
        self._small_btn(row, "Browse...", self._browse_output).pack(side="right")

    def _browse_output(self):
        path = filedialog.askdirectory(initialdir=self.var_output_dir.get(), title="Choose output folder")
        if path:
            self.var_output_dir.set(path)

    def _browse_cookies(self):
        path = filedialog.askopenfilename(title="Select YouTube cookies file", filetypes=[("Cookies / Text files", "*.txt"), ("All Files", "*.*")])
        if path:
            self.var_cookiefile.set(path)

    def _clear_cookies(self):
        self.var_cookiefile.set("")
        self.var_cookies_browser.set("None")

    def _open_output_dir(self):
        path = self.var_output_dir.get()
        os.makedirs(path, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.run(["xdg-open", path], check=False)

    def _build_run_view_section(self, parent):
        card = self._card(parent, margin_bottom=0, fill="both", expand=True)
        header = tk.Frame(card, bg=Theme.BG2, padx=12, pady=10)
        header.pack(fill="x")
        self._section_label(header, "RUN VIEW").pack(side="left")
        self.btn_progress_view = self._small_btn(header, "Progress View", lambda: self._show_run_view("progress"))
        self.btn_progress_view.pack(side="left", padx=(12, 4))
        self.btn_log_view = self._small_btn(header, "Log View", lambda: self._show_run_view("log"))
        self.btn_log_view.pack(side="left")
        self._small_btn(header, "Save Log", self._save_log).pack(side="right", padx=(0, 6))
        self._small_btn(header, "Clear Log", self._clear_logs).pack(side="right", padx=(0, 6))
        tk.Checkbutton(header, text="Auto-scroll", variable=self.var_autoscroll, bg=Theme.BG2, fg=Theme.TEXT, selectcolor=Theme.BG3, activebackground=Theme.BG2, activeforeground=Theme.TEXT, font=("Helvetica Neue", 9), relief="flat", bd=0, highlightthickness=0).pack(side="right", padx=(0, 8))
        tk.Checkbutton(header, text="Suppress JS Warn", variable=self.var_suppress_js, bg=Theme.BG2, fg=Theme.TEXT, selectcolor=Theme.BG3, activebackground=Theme.BG2, activeforeground=Theme.TEXT, font=("Helvetica Neue", 9), relief="flat", bd=0, highlightthickness=0).pack(side="right", padx=(0, 10))

        content = tk.Frame(card, bg=Theme.BG2)
        content.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.progress_view_frame = tk.Frame(content, bg=Theme.BG2)
        self.log_view_frame = tk.Frame(content, bg=Theme.BG2)
        self._build_progress_view(self.progress_view_frame)
        self._build_log_view(self.log_view_frame)
        self._show_run_view("progress")

    def _build_progress_view(self, parent):
        summary = tk.Frame(parent, bg=Theme.BG2)
        summary.pack(fill="x")
        self.lbl_current = tk.Label(summary, text="Idle", bg=Theme.BG2, fg=Theme.MUTED, font=("Courier New", 8), anchor="w")
        self.lbl_current.pack(side="left", fill="x", expand=True)
        self.lbl_progress_count = tk.Label(summary, text="0 / 0 files", bg=Theme.BG2, fg=Theme.MUTED, font=("Courier New", 9))
        self.lbl_progress_count.pack(side="right")

        self.pb_overall = ttk.Progressbar(parent, mode="determinate", style="Horizontal.TProgressbar")
        self.pb_overall.pack(fill="x", pady=(6, 10))

        active_outer = tk.Frame(parent, bg=Theme.BG2)
        active_outer.pack(fill="both", expand=True)
        self.progress_canvas = tk.Canvas(active_outer, bg=Theme.BG2, highlightthickness=0)
        self.progress_scrollbar = ttk.Scrollbar(active_outer, orient="vertical", command=self.progress_canvas.yview)
        self.active_progress_frame = tk.Frame(self.progress_canvas, bg=Theme.BG2)
        self.active_progress_frame.bind("<Configure>", lambda event: self.progress_canvas.configure(scrollregion=self.progress_canvas.bbox("all")))
        self.progress_canvas_window = self.progress_canvas.create_window((0, 0), window=self.active_progress_frame, anchor="nw")
        self.progress_canvas.bind("<Configure>", lambda event: self.progress_canvas.itemconfig(self.progress_canvas_window, width=event.width))
        self.progress_canvas.configure(yscrollcommand=self.progress_scrollbar.set)
        self.progress_canvas.pack(side="left", fill="both", expand=True)
        self.progress_scrollbar.pack(side="right", fill="y")

    def _build_log_view(self, parent):
        self.log_text = tk.Text(
            parent,
            bg=Theme.BG2,
            fg=Theme.TEXT,
            font=("Courier New", 9),
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            wrap="word",
            state="disabled",
            cursor="arrow",
            insertbackground=Theme.TEXT,
            selectbackground=Theme.BG4,
        )
        scrollbar = ttk.Scrollbar(parent, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        for level, colour in LOG_COLOURS.items():
            self.log_text.tag_configure(level, foreground=colour)
        self.log_text.tag_configure("TS", foreground="#3d4a6a")
        self.log_text.tag_configure("SRC", foreground=Theme.PURPLE)

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=Theme.BG, pady=12)
        bar.pack(fill="x", padx=24)
        self.btn_start = tk.Button(bar, text="Start Download", bg=Theme.ACCENT, fg=Theme.BG, font=("Helvetica Neue", 12, "bold"), relief="flat", bd=0, padx=22, pady=8, cursor="hand2", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_stop = tk.Button(bar, text="Stop", bg=Theme.RED, fg=Theme.WHITE, font=("Helvetica Neue", 12, "bold"), relief="flat", bd=0, padx=22, pady=8, cursor="hand2", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(8, 0))
        self.btn_retry = tk.Button(bar, text="Retry Errors", bg=Theme.BG3, fg=Theme.TEXT, font=("Helvetica Neue", 12), relief="flat", bd=0, padx=18, pady=8, cursor="hand2", command=self._retry_errors)
        self.btn_retry.pack(side="left", padx=(8, 0))

        when_done = tk.Frame(bar, bg=Theme.BG)
        when_done.pack(side="left", padx=(20, 0))
        tk.Label(when_done, text="When done:", bg=Theme.BG, fg=Theme.TEXT).pack(side="left")
        cb_when_done = ttk.Combobox(when_done, textvariable=self.var_when_done, state="readonly", width=12)
        cb_when_done["values"] = ("Do nothing", "Sleep", "Hibernate", "Shutdown", "Reboot", "Logoff")
        cb_when_done.pack(side="left", padx=(5, 0))

        self.lbl_dep_status = tk.Label(bar, text="", bg=Theme.BG, fg=Theme.MUTED, font=("Courier New", 9))
        self.lbl_dep_status.pack(side="right")
        tk.Label(bar, text="made by ad1107", bg=Theme.BG, fg=Theme.MUTED, font=("Courier New", 9)).pack(side="right", padx=(0, 15))

    def _card(self, parent, margin_bottom=0, fill="x", expand=False):
        frame = tk.Frame(parent, bg=Theme.BG2, bd=0)
        frame.pack(fill=fill, expand=expand, pady=(0, margin_bottom))
        return frame

    def _section_label(self, parent, text):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=Theme.ACCENT, font=("Courier New", 9, "bold"))

    def _small_btn(self, parent, text, cmd):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=Theme.BG3,
            fg=Theme.TEXT,
            font=("Helvetica Neue", 9),
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            activebackground=Theme.BG4,
            activeforeground=Theme.WHITE,
        )
