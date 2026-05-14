import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from models_utils import FORMATS, QUALITIES, Theme, LOG_COLOURS

class GUIBuilderMixin:

    # ── TTK Styling ───────────────────────────────────────────────────────────

    def _apply_ttk_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".",
            background=Theme.BG2, foreground=Theme.TEXT,
            troughcolor=Theme.BG3, selectbackground=Theme.ACCENT,
            selectforeground=Theme.BG, fieldbackground=Theme.BG3,
            borderwidth=0, relief="flat")
        s.configure("TCombobox",
            fieldbackground=Theme.BG3, foreground=Theme.TEXT,
            background=Theme.BG3, selectbackground=Theme.BG3,
            selectforeground=Theme.TEXT)
        s.map("TCombobox",
            fieldbackground=[("readonly", Theme.BG3)],
            foreground=[("readonly", Theme.TEXT)])
        s.configure("Horizontal.TProgressbar",
            background=Theme.ACCENT, troughcolor=Theme.BG3,
            borderwidth=0, thickness=5)
        s.configure("Green.Horizontal.TProgressbar",
            background=Theme.GREEN, troughcolor=Theme.BG3,
            borderwidth=0, thickness=5)
        s.configure("TScrollbar",
            background=Theme.BG3, troughcolor=Theme.BG2,
            arrowcolor=Theme.MUTED, borderwidth=0, width=8)

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self, bg=Theme.BG, pady=14)
        hdr.pack(fill="x", padx=24)
        tk.Label(hdr, text="YouTube Audio Downloader and Converter",      bg=Theme.BG, fg=Theme.ACCENT,
                 font=("Helvetica Neue", 22, "bold")).pack(side="left")
        self.lbl_badge = tk.Label(hdr, text="● READY", bg=Theme.BG, fg=Theme.GREEN,
                                   font=("Courier New", 10, "bold"))
        self.lbl_badge.pack(side="right")
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")

        body = tk.Frame(self, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=24, pady=16)

        left = tk.Frame(body, bg=Theme.BG, width=430)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.pack_propagate(False)
        self._build_playlist_section(left)
        self._build_output_section(left)
        self._build_settings_section(left)
        self._build_progress_section(left)

        right = tk.Frame(body, bg=Theme.BG)
        right.pack(side="right", fill="both", expand=True)
        self._build_log_section(right)

        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")
        self._build_bottom_bar()

    # ── Playlist / URL Section ────────────────────────────────────────────────

    def _build_playlist_section(self, parent):
        card = self._card(parent, margin_bottom=10)
        hrow = tk.Frame(card, bg=Theme.BG2)
        hrow.pack(fill="x", padx=12, pady=(10, 6))
        self._section_label(hrow, "URLS").pack(side="left")
        self._small_btn(hrow, "+ Add Row",  self._add_playlist_row).pack(side="right", padx=(4,0))
        self._small_btn(hrow, "Import TXT", self._import_txt).pack(side="right", padx=(4,0))
        self._small_btn(hrow, "Paste URLs", self._paste_urls).pack(side="right", padx=(4,0))
        self._small_btn(hrow, "Clear All",  self._clear_playlist_rows).pack(side="right")

        list_outer = tk.Frame(card, bg=Theme.BG2)
        list_outer.pack(fill="x", padx=12, pady=(0, 10))

        self.playlist_canvas = tk.Canvas(list_outer, bg=Theme.BG2,
                                          highlightthickness=0, bd=0, height=140)
        sb = ttk.Scrollbar(list_outer, orient="vertical",
                           command=self.playlist_canvas.yview)
        self.playlist_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.playlist_canvas.pack(side="left", fill="both", expand=True)

        self.playlist_inner = tk.Frame(self.playlist_canvas, bg=Theme.BG2)
        self.canvas_window  = self.playlist_canvas.create_window(
            (0, 0), window=self.playlist_inner, anchor="nw")
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
        tk.Label(row, text=f"{len(self.playlist_row_widgets)+1:02d}",
                 bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Courier New", 9), width=3).pack(side="left", padx=(0, 4))
        entry = tk.Entry(row, bg=Theme.BG3, fg=Theme.TEXT, relief="flat", bd=0,
                         font=("Courier New", 9), insertbackground=Theme.TEXT)
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        if url_text:
            entry.insert(0, url_text)
        def remove(r=row):
            self.playlist_row_widgets = [
                (fr, en) for fr, en in self.playlist_row_widgets if fr is not r]
            r.destroy()
            self._renumber_rows()
        tk.Button(row, text="✕", bg=Theme.BG2, fg=Theme.MUTED,
                  font=("Helvetica Neue", 11), relief="flat", bd=0, padx=6,
                  cursor="hand2", command=remove,
                  activebackground=Theme.BG2, activeforeground=Theme.RED
                  ).pack(side="right", padx=(4,0))
        self.playlist_row_widgets.append((row, entry))

    def _renumber_rows(self):
        for i, (row, _) in enumerate(self.playlist_row_widgets):
            children = row.winfo_children()
            if children:
                children[0].config(text=f"{i+1:02d}")

    def _import_txt(self):
        from tkinter import filedialog, messagebox
        filename = filedialog.askopenfilename(
            title="Select Source TXT File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filename:
            return
            
        try:
            with open(filename, "r", encoding="utf-8") as f:
                text = f.read()
            self._add_lines_to_rows(text)
        except Exception as e:
            messagebox.showerror("Read Error", f"Failed to read file: {e}")

    def _paste_urls(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        self._add_lines_to_rows(text)

    def _add_lines_to_rows(self, text: str):
        urls = [u.strip() for u in text.splitlines() if u.strip()]
        if not urls:
            return
        empty = [e for _, e in self.playlist_row_widgets if not e.get().strip()]
        for i, url in enumerate(urls):
            # Parse possible "FolderName | https..." format
            folder = ""
            if "|" in url:
                parts = url.split("|", 1)
                folder, url = parts[0].strip(), parts[1].strip()
                
            if i < len(empty) and not folder:
                empty[i].delete(0, "end"); empty[i].insert(0, url)
            else:
                self._add_playlist_row(url_text=url)
                # Note: Currently _add_playlist_row only accepts url_text, so manual folder overriding
                # isn't explicitly supported in the GUI builder row method yet. We will just add the url.

    def _clear_playlist_rows(self):
        for row, _ in self.playlist_row_widgets:
            row.destroy()
        self.playlist_row_widgets.clear()
        self._add_playlist_row()
        self._add_playlist_row()

    # ── Output Section ────────────────────────────────────────────────────────

    def _build_output_section(self, parent):
        card = self._card(parent, margin_bottom=10)
        tk.Frame(card, bg=Theme.BG2, height=1).pack(fill="x")
        hrow = tk.Frame(card, bg=Theme.BG2, padx=12, pady=8)
        hrow.pack(fill="x")
        self._section_label(hrow, "OUTPUT FOLDER").pack(anchor="w")
        irow = tk.Frame(card, bg=Theme.BG2, padx=12, pady=0)
        irow.pack(fill="x")
        tk.Entry(irow, textvariable=self.var_output_dir,
                 bg=Theme.BG3, fg=Theme.TEXT, relief="flat", bd=0,
                 font=("Courier New", 9), insertbackground=Theme.TEXT
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
        self._small_btn(irow, "Open",    self._open_output_dir).pack(side="right", padx=(0,4))
        self._small_btn(irow, "Browse…", self._browse_output).pack(side="right")

    def _browse_output(self):
        path = filedialog.askdirectory(initialdir=self.var_output_dir.get(),
                                       title="Choose output folder")
        if path: self.var_output_dir.set(path)

    def _open_output_dir(self):
        path = self.var_output_dir.get()
        os.makedirs(path, exist_ok=True)
        if   sys.platform == "darwin": subprocess.run(["open",     path])
        elif sys.platform == "win32":  os.startfile(path)
        else:                          subprocess.run(["xdg-open", path])

    # ── Settings Section ──────────────────────────────────────────────────────

    def _build_settings_section(self, parent):
        card = self._card(parent, margin_bottom=10)
        hrow = tk.Frame(card, bg=Theme.BG2, padx=12, pady=10)
        hrow.pack(fill="x")
        self._section_label(hrow, "SETTINGS").pack(anchor="w")

        body  = tk.Frame(card, bg=Theme.BG2, padx=12)
        body.pack(fill="x", pady=(0, 8))
        LBL_W = 15

        r = tk.Frame(body, bg=Theme.BG2); r.pack(fill="x", pady=3)
        tk.Label(r, text="Format", bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Helvetica Neue", 10), width=LBL_W, anchor="w").pack(side="left")
        ttk.Combobox(r, textvariable=self.var_format, values=list(FORMATS.keys()),
                     state="readonly", font=("Helvetica Neue", 10), width=30).pack(side="left")

        r = tk.Frame(body, bg=Theme.BG2); r.pack(fill="x", pady=3)
        tk.Label(r, text="Quality", bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Helvetica Neue", 10), width=LBL_W, anchor="w").pack(side="left")
        self.cb_quality = ttk.Combobox(r, textvariable=self.var_quality, values=list(QUALITIES.keys()),
                     state="readonly", font=("Helvetica Neue", 10), width=22)
        self.cb_quality.pack(side="left")

        # ── Setup Trace for Lossless Formats ──
        def _on_format_change(*args):
            fmt_name = self.var_format.get()
            fmt_code = FORMATS.get(fmt_name, "m4a")
            if fmt_code in ["flac", "wav", "alac", "aiff"]:
                self.cb_quality.config(state="disabled")
            else:
                self.cb_quality.config(state="readonly")
        
        self.var_format.trace_add("write", _on_format_change)
        # initial trigger
        _on_format_change()

        r = tk.Frame(body, bg=Theme.BG2); r.pack(fill="x", pady=3)
        tk.Label(r, text="Playback Speed", bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Helvetica Neue", 10), width=LBL_W, anchor="w").pack(side="left")
        ttk.Combobox(r, textvariable=self.var_speed, values=[0.5, 0.75, 1.0, 1.1, 1.25, 1.3, 1.5, 1.75, 2.0],
                     state="readonly", font=("Helvetica Neue", 10), width=8).pack(side="left")
        tk.Label(r, text="x (Retains pitch, 1.0=Normal)", bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Helvetica Neue", 9)).pack(side="left", padx=(6,0))

        # Bug 3 FIX: the old playlist/single-video toggle checkbox has been removed.
        # URL type is now auto-detected from the link structure at download time.

        r = tk.Frame(body, bg=Theme.BG2); r.pack(fill="x", pady=3)
        tk.Label(r, text="Concurrent DLs", bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Helvetica Neue", 10), width=LBL_W, anchor="w").pack(side="left")
        tk.Spinbox(r, textvariable=self.var_concurrent,
                   from_=1, to=8, width=4, bg=Theme.BG3, fg=Theme.TEXT,
                   relief="flat", bd=0, font=("Courier New", 10),
                   insertbackground=Theme.TEXT,
                   buttonbackground=Theme.BG4).pack(side="left")
        tk.Label(r, text="(jobs at once)", bg=Theme.BG2, fg=Theme.MUTED,
                 font=("Helvetica Neue", 9)).pack(side="left", padx=(6,0))

        cb_frame = tk.Frame(body, bg=Theme.BG2)
        cb_frame.pack(fill="x", pady=(8,0))
        for i, (label, var) in enumerate([
            ("Embed Thumbnail",  self.var_thumbnail),
            ("Crop to Square",   self.var_crop_thumb),
            ("Embed Metadata",   self.var_metadata),
            ("Number Tracks",    self.var_track_num),
            ("Skip Existing",    self.var_skip_existing),
        ]):
            tk.Checkbutton(cb_frame, text=label, variable=var,
                           bg=Theme.BG2, fg=Theme.TEXT,
                           selectcolor=Theme.BG3, activebackground=Theme.BG2,
                           activeforeground=Theme.TEXT, font=("Helvetica Neue", 10),
                           bd=0, cursor="hand2", highlightthickness=0
                           ).grid(row=i//2, column=i%2, sticky="w", padx=(0,12), pady=1)

    # ── Progress Section ──────────────────────────────────────────────────────

    def _build_progress_section(self, parent):
        card = self._card(parent, margin_bottom=0)
        card.pack(fill="both", expand=True) # override the pack from _card to allow expansion
        hrow = tk.Frame(card, bg=Theme.BG2, padx=12, pady=10)
        hrow.pack(fill="x")
        self._section_label(hrow, "PROGRESS").pack(side="left")
        self.lbl_progress_count = tk.Label(hrow, text="0 / 0 files",
                                            bg=Theme.BG2, fg=Theme.MUTED,
                                            font=("Courier New", 9))
        self.lbl_progress_count.pack(side="right")

        pbody = tk.Frame(card, bg=Theme.BG2, padx=12, pady=0)
        pbody.pack(fill="x")
        self.pb_overall = ttk.Progressbar(pbody, mode="determinate",
                                           style="Horizontal.TProgressbar")
        self.pb_overall.pack(fill="x")
        self.lbl_current = tk.Label(pbody, text="Idle", bg=Theme.BG2, fg=Theme.MUTED,
                                     font=("Courier New", 8), anchor="w", wraplength=390)
        self.lbl_current.pack(fill="x", pady=(4,2))

        # Add scrollbar to the progress bars list
        progress_container = tk.Frame(card, bg=Theme.BG2, padx=12)
        progress_container.pack(fill="both", expand=True, pady=(0, 10))
        
        self.progress_canvas = tk.Canvas(progress_container, bg=Theme.BG2, highlightthickness=0, height=200)
        self.progress_scrollbar = ttk.Scrollbar(progress_container, orient="vertical", command=self.progress_canvas.yview)
        
        self.playlist_progress_frame = tk.Frame(self.progress_canvas, bg=Theme.BG2)
        
        self.playlist_progress_frame.bind(
            "<Configure>",
            lambda e: self.progress_canvas.configure(scrollregion=self.progress_canvas.bbox("all"))
        )
        self.progress_canvas_window = self.progress_canvas.create_window((0, 0), window=self.playlist_progress_frame, anchor="nw")
        
        self.progress_canvas.pack(side="left", fill="both", expand=True)
        self.progress_scrollbar.pack(side="right", fill="y")
        self.progress_canvas.configure(yscrollcommand=self.progress_scrollbar.set)
        
        # Bind canvas resize to update inner frame width
        self.progress_canvas.bind(
            "<Configure>",
            lambda e: self.progress_canvas.itemconfig(self.progress_canvas_window, width=e.width)
        )

    # ── Log Section ───────────────────────────────────────────────────────────

    def _build_log_section(self, parent):
        hrow = tk.Frame(parent, bg=Theme.BG)
        hrow.pack(fill="x", pady=(0, 8))
        self._section_label(hrow, "ACTIVITY LOG").pack(side="left")
        self._small_btn(hrow, "Save Log…", self._save_log).pack(side="right", padx=(0,6))
        self._small_btn(hrow, "Clear",      self._clear_logs).pack(side="right")

        log_card = tk.Frame(parent, bg=Theme.BG2)
        log_card.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_card, bg=Theme.BG2, fg=Theme.TEXT,
                                 font=("Courier New", 9), relief="flat", bd=0,
                                 padx=10, pady=8, wrap="word", state="disabled",
                                 cursor="arrow", insertbackground=Theme.TEXT,
                                 selectbackground=Theme.BG4)
        sb = ttk.Scrollbar(log_card, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)
        for lvl, col in LOG_COLOURS.items():
            self.log_text.tag_configure(lvl, foreground=col)
        self.log_text.tag_configure("TS",  foreground="#3d4a6a")
        self.log_text.tag_configure("SRC", foreground=Theme.PURPLE)

    # ── Bottom Bar ────────────────────────────────────────────────────────────

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=Theme.BG, pady=12)
        bar.pack(fill="x", padx=24)
        self.btn_start = tk.Button(bar, text="▶  Start Download",
                                    bg=Theme.ACCENT, fg=Theme.BG,
                                    font=("Helvetica Neue", 12, "bold"),
                                    relief="flat", bd=0, padx=22, pady=8,
                                    cursor="hand2", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_stop = tk.Button(bar, text="■  Stop",
                                   bg=Theme.RED, fg=Theme.WHITE,
                                   font=("Helvetica Neue", 12, "bold"),
                                   relief="flat", bd=0, padx=22, pady=8,
                                   cursor="hand2", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(8,0))
        
        # When done dropdown
        frame_when_done = tk.Frame(bar, bg=Theme.BG)
        frame_when_done.pack(side="left", padx=(20, 0))
        tk.Label(frame_when_done, text="When done, do:", bg=Theme.BG, fg=Theme.TEXT).pack(side="left")
        cb_when_done = ttk.Combobox(frame_when_done, textvariable=self.var_when_done, state="readonly", width=12)
        cb_when_done['values'] = ("Do nothing", "Sleep", "Hibernate", "Shutdown", "Reboot", "Logoff")
        cb_when_done.pack(side="left", padx=(5, 0))

        self.lbl_dep_status = tk.Label(bar, text="", bg=Theme.BG, fg=Theme.MUTED,
                                        font=("Courier New", 9))
        self.lbl_dep_status.pack(side="right")
        
        lbl_made_by = tk.Label(bar, text="made by ad1107", bg=Theme.BG, fg=Theme.MUTED, font=("Courier New", 9))
        lbl_made_by.pack(side="right", padx=(0, 15))
    def _card(self, parent, margin_bottom=0):
        f = tk.Frame(parent, bg=Theme.BG2, bd=0)
        f.pack(fill="x", pady=(0, margin_bottom))
        return f

    def _section_label(self, parent, text):
        return tk.Label(parent, text=text, bg=parent.cget("bg"),
                        fg=Theme.ACCENT, font=("Courier New", 9, "bold"))

    def _small_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg=Theme.BG3, fg=Theme.TEXT,
                         font=("Helvetica Neue", 9), relief="flat", bd=0,
                         padx=8, pady=3, cursor="hand2",
                         activebackground=Theme.BG4, activeforeground=Theme.WHITE)