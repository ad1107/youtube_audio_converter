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
        self.job_progress_widgets = {}
        self.item_progress_widgets = {}

    def _progress_key(self, job, item) -> str:
        return f"{job.job_id}:{item.index}"

    def _set_job_progress(self, job, percent: float | None = None, status: str | None = None, style: str | None = None):
        def apply():
            widgets = self._ensure_job_progress_widget(job)
            total = job.total_videos or 0
            done = job.completed_videos + job.failed_videos
            value = percent if percent is not None else (done / total * 100 if total else 0)
            widgets["bar"].configure(value=max(0, min(100, value)))
            if style:
                widgets["bar"].configure(style=style)
            if status:
                widgets["status"].config(text=status)
            else:
                widgets["status"].config(text=f"{done}/{total}" if total else "Fetching")
            widgets["title"].config(text=f"#{job.job_id + 1} {job.playlist_title[:62]}")

        self.after(0, apply)

    def _set_active_progress(self, job, item, phase: str, percent: float | None, status: str, detail: str = ""):
        key = self._progress_key(job, item)

        def apply():
            self._ensure_job_progress_widget(job)
            widgets = self._ensure_item_progress_widget(key, job, item)
            style = "Convert.Horizontal.TProgressbar" if phase == "convert" else "Download.Horizontal.TProgressbar"
            widgets["bar"].configure(style=style, mode="determinate")
            if percent is not None:
                widgets["bar"].configure(value=max(0, min(100, percent)))
            widgets["status"].config(text=status)
            if detail:
                widgets["detail"].config(text=detail)

        self.after(0, apply)

    def _mark_active_done(self, job, item, detail: str):
        key = self._progress_key(job, item)

        def apply():
            widgets = self._ensure_item_progress_widget(key, job, item)
            widgets["bar"].configure(style="Green.Horizontal.TProgressbar", value=100)
            widgets["status"].config(text="Done")
            widgets["title"].config(fg=Theme.GREEN)
            widgets["detail"].config(text=detail)

        self.after(0, apply)

    def _mark_active_skipped(self, job, item, detail: str):
        key = self._progress_key(job, item)

        def apply():
            widgets = self._ensure_item_progress_widget(key, job, item)
            widgets["bar"].configure(style="Green.Horizontal.TProgressbar", value=100)
            widgets["status"].config(text="Skipped")
            widgets["title"].config(fg=Theme.MUTED)
            widgets["detail"].config(text=detail)

        self.after(0, apply)

    def _remove_active_progress(self, job, item, delay_ms: int = 700):
        self._mark_active_done(job, item, f"Saved: {item.expected_path}")

    def _mark_active_failed(self, job, item, status: str):
        if item is None:
            return
        key = self._progress_key(job, item)

        def apply():
            widgets = self._ensure_item_progress_widget(key, job, item)
            widgets["bar"].configure(style="Error.Horizontal.TProgressbar", value=100)
            widgets["status"].config(text=status)
            widgets["title"].config(fg=Theme.RED)
            widgets["detail"].config(text=f"Source: {item.url}")

        self.after(0, apply)

    def _ensure_job_progress_widget(self, job) -> dict:
        widgets = self.job_progress_widgets.get(job.job_id)
        if widgets:
            return widgets

        frame = tk.Frame(self.active_progress_frame, bg=Theme.BG2)
        frame.pack(fill="x", pady=(0, 12))

        top = tk.Frame(frame, bg=Theme.BG2)
        top.pack(fill="x")
        title = tk.Label(
            top,
            text=f"#{job.job_id + 1} {job.playlist_title[:62]}",
            bg=Theme.BG2,
            fg=Theme.TEXT,
            font=("Courier New", 9, "bold"),
            anchor="w",
        )
        title.pack(side="left", fill="x", expand=True)
        status = tk.Label(
            top,
            text="Fetching",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Courier New", 8),
            anchor="e",
            width=16,
        )
        status.pack(side="right")

        bar = ttk.Progressbar(frame, mode="determinate", style="Horizontal.TProgressbar")
        bar.pack(fill="x", pady=(4, 5))

        items_frame = tk.Frame(frame, bg=Theme.BG2, padx=14)
        items_frame.pack(fill="x")

        widgets = {"frame": frame, "title": title, "status": status, "bar": bar, "items_frame": items_frame}
        self.job_progress_widgets[job.job_id] = widgets
        return widgets

    def _ensure_item_progress_widget(self, key: str, job, item) -> dict:
        widgets = self.item_progress_widgets.get(key)
        if widgets:
            return widgets

        job_widgets = self._ensure_job_progress_widget(job)
        frame = tk.Frame(job_widgets["items_frame"], bg=Theme.BG2)
        frame.pack(fill="x", pady=(0, 8))

        top = tk.Frame(frame, bg=Theme.BG2)
        top.pack(fill="x")
        title = tk.Label(
            top,
            text=f"{item.index:02d}. {item.title[:58]}",
            bg=Theme.BG2,
            fg=Theme.TEXT,
            font=("Courier New", 8),
            anchor="w",
        )
        title.pack(side="left", fill="x", expand=True)
        status = tk.Label(
            top,
            text="Queued",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Courier New", 8),
            anchor="e",
            width=18,
        )
        status.pack(side="right")

        bar = ttk.Progressbar(frame, mode="determinate", style="Download.Horizontal.TProgressbar")
        bar.pack(fill="x", pady=(3, 2))
        detail = tk.Label(
            frame,
            text=f"Source: {item.url}",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Courier New", 8),
            anchor="w",
            justify="left",
            wraplength=640,
        )
        detail.pack(fill="x")

        widgets = {"frame": frame, "title": title, "status": status, "bar": bar, "detail": detail}
        self.item_progress_widgets[key] = widgets
        return widgets
