import tkinter as tk
from tkinter import ttk

from .models import Theme


class GUIProgressMixin:
    def _build_progress_view(self, parent):
        summary = tk.Frame(parent, bg=Theme.BG2)
        summary.pack(fill="x")
        self.lbl_current = tk.Label(
            summary,
            text="Idle",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Courier New", 8),
            anchor="w",
        )
        self.lbl_current.pack(side="left", fill="x", expand=True)
        tk.Checkbutton(
            summary,
            text="Hide inactive tasks",
            variable=self.var_hide_inactive_tasks,
            command=self._on_hide_inactive_tasks_changed,
            bg=Theme.BG2,
            fg=Theme.TEXT,
            selectcolor=Theme.BG3,
            activebackground=Theme.BG2,
            activeforeground=Theme.TEXT,
            font=("Helvetica Neue", 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
        ).pack(side="right", padx=(10, 0))
        self.lbl_progress_count = tk.Label(
            summary,
            text="0 / 0 files",
            bg=Theme.BG2,
            fg=Theme.MUTED,
            font=("Courier New", 9),
        )
        self.lbl_progress_count.pack(side="right")

        self.pb_overall = ttk.Progressbar(parent, mode="determinate", style="Horizontal.TProgressbar")
        self.pb_overall.pack(fill="x", pady=(6, 10))

        active_outer = tk.Frame(parent, bg=Theme.BG2)
        active_outer.pack(fill="both", expand=True)
        self.progress_canvas = tk.Canvas(active_outer, bg=Theme.BG2, highlightthickness=0)
        self.progress_scrollbar = ttk.Scrollbar(active_outer, orient="vertical", command=self.progress_canvas.yview)
        self.active_progress_frame = tk.Frame(self.progress_canvas, bg=Theme.BG2)
        self.active_progress_frame.bind("<Configure>", lambda event: self._schedule_progress_scrollregion_update())
        self.progress_canvas_window = self.progress_canvas.create_window((0, 0), window=self.active_progress_frame, anchor="nw")
        self.progress_canvas.bind("<Configure>", self._on_progress_canvas_configure)
        self.progress_canvas.configure(yscrollcommand=self.progress_scrollbar.set)
        self.progress_canvas.pack(side="left", fill="both", expand=True)
        self.progress_scrollbar.pack(side="right", fill="y")

    def _on_progress_canvas_configure(self, event):
        self.progress_canvas.itemconfig(self.progress_canvas_window, width=event.width)
        self._schedule_progress_scrollregion_update()

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
        self.item_progress_states = {}

    def _on_hide_inactive_tasks_changed(self):
        self._refresh_item_progress_visibility()

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

    def _set_active_progress(
        self,
        job,
        item,
        phase: str,
        percent: float | None,
        status: str,
        detail: str = "",
        active: bool = True,
    ):
        key = self._progress_key(job, item)

        def apply():
            self._ensure_job_progress_widget(job)
            style = "Convert.Horizontal.TProgressbar" if phase == "convert" else "Download.Horizontal.TProgressbar"
            self._save_item_progress_state(
                key=key,
                job=job,
                item=item,
                phase=phase,
                percent=percent,
                status=status,
                detail=detail,
                bar_style=style,
                title_fg=Theme.TEXT,
                active=active,
            )
            self._sync_item_progress_widget(key)

        self.after(0, apply)

    def _mark_active_done(self, job, item, detail: str):
        key = self._progress_key(job, item)

        def apply():
            self._save_item_progress_state(
                key=key,
                job=job,
                item=item,
                phase="done",
                percent=100,
                status="Done",
                detail=detail,
                bar_style="Green.Horizontal.TProgressbar",
                title_fg=Theme.GREEN,
                active=False,
            )
            self._sync_item_progress_widget(key)

        self.after(0, apply)

    def _mark_active_skipped(self, job, item, detail: str):
        key = self._progress_key(job, item)

        def apply():
            self._save_item_progress_state(
                key=key,
                job=job,
                item=item,
                phase="skipped",
                percent=100,
                status="Skipped",
                detail=detail,
                bar_style="Green.Horizontal.TProgressbar",
                title_fg=Theme.MUTED,
                active=False,
            )
            self._sync_item_progress_widget(key)

        self.after(0, apply)

    def _mark_active_failed(self, job, item, status: str):
        if item is None:
            return
        key = self._progress_key(job, item)

        def apply():
            self._save_item_progress_state(
                key=key,
                job=job,
                item=item,
                phase="failed",
                percent=100,
                status=status,
                detail=f"Source: {item.url}",
                bar_style="Error.Horizontal.TProgressbar",
                title_fg=Theme.RED,
                active=False,
            )
            self._sync_item_progress_widget(key)

        self.after(0, apply)

    def _save_item_progress_state(
        self,
        key: str,
        job,
        item,
        phase: str,
        percent: float | None,
        status: str,
        detail: str,
        bar_style: str,
        title_fg: str,
        active: bool,
    ) -> dict:
        state = self.item_progress_states.get(key, {})
        state.update(
            {
                "job": job,
                "item": item,
                "phase": phase,
                "percent": percent,
                "status": status,
                "detail": detail,
                "bar_style": bar_style,
                "title_fg": title_fg,
                "active": active,
            }
        )
        self.item_progress_states[key] = state
        return state

    def _sync_item_progress_widget(self, key: str):
        state = self.item_progress_states.get(key)
        if not state:
            return

        if self._should_hide_item_progress(state):
            self._destroy_item_progress_widget(key)
            self._schedule_progress_scrollregion_update()
            return

        widgets = self._ensure_item_progress_widget(key, state["job"], state["item"])
        self._pack_item_progress_widget(widgets)
        self._apply_item_progress_state(widgets, state)
        self._schedule_progress_scrollregion_update()

    def _refresh_item_progress_visibility(self):
        for widgets in list(self.item_progress_widgets.values()):
            widgets["frame"].pack_forget()
        for key in sorted(self.item_progress_states, key=self._progress_sort_key):
            self._sync_item_progress_widget(key)
        self._schedule_progress_scrollregion_update()

    def _progress_sort_key(self, key: str) -> tuple[int, int]:
        try:
            job_id, item_index = key.split(":", 1)
            return int(job_id), int(item_index)
        except (TypeError, ValueError):
            return 0, 0

    def _should_hide_item_progress(self, state: dict) -> bool:
        return bool(self.var_hide_inactive_tasks.get() and not state.get("active"))

    def _pack_item_progress_widget(self, widgets: dict):
        if not widgets["frame"].winfo_manager():
            widgets["frame"].pack(fill="x", pady=(0, 8))

    def _destroy_item_progress_widget(self, key: str):
        widgets = self.item_progress_widgets.pop(key, None)
        if widgets:
            parent = widgets["frame"].master
            widgets["frame"].destroy()
            self._collapse_empty_items_frame(parent)

    def _collapse_empty_items_frame(self, frame):
        if frame and not frame.winfo_children():
            frame.configure(height=1)

    def _schedule_progress_scrollregion_update(self):
        if getattr(self, "_progress_scrollregion_pending", False):
            return
        self._progress_scrollregion_pending = True
        self.after_idle(self._update_progress_scrollregion)

    def _update_progress_scrollregion(self):
        self._progress_scrollregion_pending = False
        try:
            self.update_idletasks()
            self.progress_canvas.configure(scrollregion=self.progress_canvas.bbox("all") or (0, 0, 0, 0))
        except tk.TclError:
            pass

    def _apply_item_progress_state(self, widgets: dict, state: dict):
        widgets["bar"].configure(style=state["bar_style"], mode="determinate")
        percent = state.get("percent")
        if percent is not None:
            widgets["bar"].configure(value=max(0, min(100, percent)))
        widgets["status"].config(text=state["status"])
        widgets["title"].config(fg=state["title_fg"])
        if state.get("detail"):
            widgets["detail"].config(text=state["detail"])

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
