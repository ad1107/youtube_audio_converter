import queue
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
import tkinter as tk
from tkinter import ttk

from .models import LOG_COLOURS, Theme


class GUILogMixin:
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

    def _poll_log_queue(self):
        entries = []
        try:
            while True:
                entries.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        if entries:
            self._write_log_batch(entries)
        self.after(40, self._poll_log_queue)

    def _write_log(self, source: str, message: str, level: str, ts: datetime):
        self._write_log_batch([(source, message, level, ts)])

    def _write_log_batch(self, entries):
        self.log_text.config(state="normal")
        for source, message, level, ts in entries:
            level_tag = level if level in LOG_COLOURS else "INFO"
            self.log_text.insert("end", f"[{ts.strftime('%H:%M:%S')}] ", "TS")
            self.log_text.insert("end", f"[{level:<8s}] ", level_tag)
            if source and source.upper() != "SYSTEM":
                self.log_text.insert("end", f"[{source[:38]:<38s}] ", "SRC")
            self.log_text.insert("end", f"{message}\n", level_tag)
        if hasattr(self, "var_autoscroll") and self.var_autoscroll.get():
            self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All", "*.*")],
            initialfile=f"audiobook_log_{datetime.now():%Y%m%d_%H%M%S}.txt",
        )
        if path:
            Path(path).write_text(self.log_text.get("1.0", "end"), encoding="utf-8")
            self.log("SYSTEM", f"Log saved -> {path}", "SUCCESS")
