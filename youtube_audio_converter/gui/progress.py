import tkinter as tk
from tkinter import ttk

from .models import Theme


class GUIProgressMixin:
    def _show_run_view(self, view: str):
        self.var_run_view.set(view)
        if view == "log":
            self.progress_view_frame.pack_forget()
            self.log_view_frame.pack(fill="both", expand=True)
            self.btn_progress_view.config(bg=Theme.BG3, fg=Theme.TEXT)
            self.btn_log_view.config(bg=Theme.ACCENT, fg=Theme.BG)
            return

        self.log_view_frame.pack_forget()
        self.progress_view_frame.pack(fill="both", expand=True)
        self.btn_progress_view.config(bg=Theme.ACCENT, fg=Theme.BG)
        self.btn_log_view.config(bg=Theme.BG3, fg=Theme.TEXT)

    def _clear_active_progress(self):
        for widget in self.active_progress_frame.winfo_children():
            widget.destroy()
        self.active_progress_widgets = {}

    def _progress_key(self, job, item) -> str:
        return f"{job.job_id}:{item.index}"

    def _set_active_progress(self, job, item, phase: str, percent: float | None, status: str):
        key = self._progress_key(job, item)

        def apply():
            widgets = self._ensure_active_progress_widget(key, job, item)
            style = "Convert.Horizontal.TProgressbar" if phase == "convert" else "Download.Horizontal.TProgressbar"
            bar = widgets["bar"]
            bar.configure(style=style, mode="determinate")
            if percent is not None:
                bar.configure(value=max(0, min(100, percent)))
            widgets["status"].config(text=status)

        self.after(0, apply)

    def _remove_active_progress(self, job, item, delay_ms: int = 700):
        key = self._progress_key(job, item)

        def remove():
            widgets = self.active_progress_widgets.pop(key, None)
            if widgets:
                widgets["frame"].destroy()

        self.after(delay_ms, remove)

    def _mark_active_failed(self, job, item, status: str):
        if item is None:
            return
        key = self._progress_key(job, item)

        def apply():
            widgets = self._ensure_active_progress_widget(key, job, item)
            widgets["bar"].configure(style="Error.Horizontal.TProgressbar", value=100)
            widgets["status"].config(text=status)
            widgets["title"].config(fg=Theme.RED)

        self.after(0, apply)
        self._remove_active_progress(job, item, delay_ms=1800)

    def _ensure_active_progress_widget(self, key: str, job, item) -> dict:
        widgets = self.active_progress_widgets.get(key)
        if widgets:
            return widgets

        frame = tk.Frame(self.active_progress_frame, bg=Theme.BG2)
        frame.pack(fill="x", pady=(0, 8))

        top = tk.Frame(frame, bg=Theme.BG2)
        top.pack(fill="x")
        title = tk.Label(
            top,
            text=f"{job.playlist_title[:34]} - {item.title[:46]}",
            bg=Theme.BG2,
            fg=Theme.TEXT,
            font=("Courier New", 8),
            anchor="w",
        )
        title.pack(side="left", fill="x", expand=True)
        status = tk.Label(
            top,
            text="Starting",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Courier New", 8),
            anchor="e",
            width=18,
        )
        status.pack(side="right")

        bar = ttk.Progressbar(frame, mode="determinate", style="Download.Horizontal.TProgressbar")
        bar.pack(fill="x", pady=(3, 0))

        widgets = {"frame": frame, "title": title, "status": status, "bar": bar}
        self.active_progress_widgets[key] = widgets
        return widgets
