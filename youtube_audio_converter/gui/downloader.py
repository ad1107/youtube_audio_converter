import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from youtube_audio_converter.core.download import DownloadCallbacks, DownloadSettings, run_download_job, summarize_elapsed
from youtube_audio_converter.core.formatting import fmt_duration, fmt_speed
from youtube_audio_converter.core.runtime import DownloadRuntime
from youtube_audio_converter.core.urls import parse_source_line
from youtube_audio_converter.dependencies import get_ffmpeg_path
from .models import FORMATS, LOG_COLOURS, QUALITIES, PlaylistJob, Theme


class GUIDownloaderMixin:
    def _poll_log_queue(self):
        try:
            while True:
                self._write_log(*self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(40, self._poll_log_queue)

    def _write_log(self, source: str, message: str, level: str, ts: datetime):
        self.log_text.config(state="normal")
        lvl_tag = level if level in LOG_COLOURS else "INFO"
        self.log_text.insert("end", f"[{ts.strftime('%H:%M:%S')}] ", "TS")
        self.log_text.insert("end", f"[{level:<8s}] ", lvl_tag)
        if source and source.upper() != "SYSTEM":
            self.log_text.insert("end", f"[{source[:38]:<38s}] ", "SRC")
        self.log_text.insert("end", f"{message}\n", lvl_tag)
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

    def _retry_errors(self):
        failed = list(getattr(self, "failed_items", []))
        urls = [
            item.get("url") if isinstance(item, dict) else getattr(item, "url", "")
            for item in failed
        ]
        urls = [url for url in urls if url]
        if not urls:
            messagebox.showinfo("Retry Errors", "No failed items to retry.")
            return

        for row, _ in self.playlist_row_widgets:
            row.destroy()
        self.playlist_row_widgets.clear()
        for url in urls:
            self._add_playlist_row(url_text=url)

        self.failed_items.clear()
        self.log("SYSTEM", f"Loaded {len(urls)} failed URL(s) into the queue.", "INFO")

    def _start(self):
        if yt_dlp is None:
            messagebox.showerror("Missing yt-dlp", "yt-dlp not installed.\npip install yt-dlp")
            return
        if not get_ffmpeg_path():
            messagebox.showerror("Missing FFmpeg", "FFmpeg not found.\nhttps://ffmpeg.org/download.html")
            return

        sources = []
        for _, entry in self.playlist_row_widgets:
            text = entry.get().strip()
            if not text:
                continue
            sources.append(parse_source_line(text) or (None, text))
        if not sources:
            messagebox.showwarning("No URLs", "Please add at least one YouTube URL.")
            return

        out_dir = self.var_output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("No Output", "Please set an output folder.")
            return

        cookiefile = getattr(self, "var_cookiefile", tk.StringVar(value="")).get().strip()
        if cookiefile and not os.path.isfile(cookiefile):
            messagebox.showerror("Invalid Cookies File", f"Cookies file not found:\n{cookiefile}")
            return

        fmt = FORMATS.get(self.var_format.get(), "m4a")
        quality = QUALITIES.get(self.var_quality.get(), "0")
        speed = float(self.var_speed.get() or 1.0)
        volume = float(self.var_volume.get() or 1.0)
        if volume <= 0:
            messagebox.showwarning("Invalid Volume", "Volume must be greater than 0.")
            return
        os.makedirs(out_dir, exist_ok=True)

        self.cancel_flag.clear()
        self.is_running = True
        self._set_system_sleep_state(prevent=True)

        self.jobs = []
        for index, (label, url) in enumerate(sources):
            job = PlaylistJob(url=url, output_dir=out_dir, fmt=fmt, quality=quality, speed=speed, job_id=index, label=label)
            job.volume = volume
            self.jobs.append(job)

        self.pb_overall["value"] = 0
        self.lbl_progress_count.config(text="0 / ? files")
        self.lbl_current.config(text="Starting...")
        for widget in self.playlist_progress_frame.winfo_children():
            widget.destroy()

        self.job_progress_bars = {}
        self.job_progress_labels = {}
        for job in self.jobs:
            frame = tk.Frame(self.playlist_progress_frame, bg=Theme.BG2)
            frame.pack(fill="x", pady=2)
            label = tk.Label(
                frame,
                text=f"#{job.job_id + 1} Fetching...",
                bg=Theme.BG2,
                fg=Theme.MUTED,
                font=("Courier New", 8),
                anchor="w",
            )
            label.pack(fill="x")
            bar = ttk.Progressbar(frame, mode="indeterminate", style="Horizontal.TProgressbar")
            bar.pack(fill="x")
            bar.start(15)
            self.job_progress_bars[job.job_id] = bar
            self.job_progress_labels[job.job_id] = label

        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_badge.config(text="DOWNLOADING", fg=Theme.YELLOW)
        threading.Thread(target=self._run_all, daemon=True).start()

    def _stop(self):
        self.cancel_flag.set()
        self.log("SYSTEM", "Stop requested; finishing current file then halting...", "WARNING")
        self.btn_stop.config(state="disabled")
        self.lbl_badge.config(text="STOPPING...", fg=Theme.YELLOW)

    def _run_all(self):
        download_slots = max(1, int(self.var_concurrent_downloads.get() or 1))
        convert_slots = max(1, int(self.var_concurrent_converts.get() or 1))
        start_delay = max(0.0, float(self.var_download_start_delay.get() or 0.0))
        self.download_runtime = DownloadRuntime(download_slots, convert_slots, start_delay)
        self.failed_items = []
        self.failed_items_lock = threading.Lock()

        self.log(
            "SYSTEM",
            f"Launching {len(self.jobs)} source(s), DL {download_slots}, convert {convert_slots}, start gap {start_delay:g}s",
            "INFO",
        )
        with ThreadPoolExecutor(max_workers=max(1, len(self.jobs))) as executor:
            future_map = {executor.submit(self._download_job, job): job for job in self.jobs}
            for future in as_completed(future_map):
                job = future_map[future]
                try:
                    future.result()
                except Exception as exc:
                    if not self.cancel_flag.is_set():
                        job.status = "error"
                        job.error_msg = str(exc)
                        self.log(job.playlist_title, f"Unhandled error: {exc}", "ERROR")
        self._on_all_finished()

    def _download_job(self, job: PlaylistJob):
        settings = DownloadSettings(
            output_dir=job.output_dir,
            fmt=job.fmt,
            quality=job.quality,
            speed=job.speed,
            volume=getattr(job, "volume", 1.0),
            cookiefile=getattr(self, "var_cookiefile", tk.StringVar(value="")).get().strip(),
            cookies_browser=getattr(self, "var_cookies_browser", tk.StringVar(value="None")).get().strip(),
            use_deno=bool(getattr(self, "var_use_deno", tk.BooleanVar(value=False)).get()),
            embed_thumbnail=bool(self.var_thumbnail.get()),
            crop_thumbnail=bool(self.var_crop_thumb.get()),
            embed_metadata=bool(self.var_metadata.get()),
            track_num=bool(self.var_track_num.get()),
            skip_existing=bool(self.var_skip_existing.get()),
            suppress_js_warnings=bool(getattr(self, "var_suppress_js", tk.BooleanVar(value=True)).get()),
            max_retries=5,
            concurrent_downloads=max(1, int(self.var_concurrent_downloads.get() or 1)),
            concurrent_converts=max(1, int(self.var_concurrent_converts.get() or 1)),
            download_start_delay=max(0.0, float(self.var_download_start_delay.get() or 0.0)),
            runtime=self.download_runtime,
        )
        callbacks = DownloadCallbacks(
            log=self.log,
            is_cancelled=self.cancel_flag.is_set,
            on_metadata=self._on_job_metadata,
            on_item_started=self._on_item_started,
            on_item_skipped=self._on_item_skipped,
            on_item_done=self._on_item_done,
            on_item_failed=self._on_item_failed,
            on_download_progress=self._progress_hook,
            on_postprocessor=self._pp_hook,
            on_ffmpeg_progress=self._ffmpeg_progress_hook,
        )
        run_download_job(job, settings, callbacks)
        self._finish_job_ui(job)

    def _on_job_metadata(self, job: PlaylistJob, title: str, total: int, output_folder: str):
        self.after(0, lambda j=job: self.job_progress_labels[j.job_id].config(
            text=f"#{j.job_id + 1} {j.playlist_title[:30]} - 0/{j.total_videos}"))
        self.after(0, lambda j=job: self.job_progress_bars[j.job_id].stop())
        self.after(0, lambda j=job: self.job_progress_bars[j.job_id].configure(mode="determinate", value=0))

    def _on_item_started(self, job: PlaylistJob, item, index: int):
        self.after(0, lambda j=job, it=item: self.lbl_current.config(text=f"{j.playlist_title}: {it.title[:52]}"))

    def _on_item_skipped(self, job: PlaylistJob, item, path: str):
        self._update_overall()
        self._update_job_progress(job)

    def _on_item_done(self, job: PlaylistJob, item, path: str):
        self._update_overall()
        self._update_job_progress(job)
        self.log(job.playlist_title, f"Saved: {item.title}", "SUCCESS")

    def _on_item_failed(self, job: PlaylistJob, item, failure):
        failed = failure.as_dict() if hasattr(failure, "as_dict") else dict(failure)
        with getattr(self, "failed_items_lock", threading.Lock()):
            self.failed_items.append(failed)
        self._update_job_progress(job)

    def _progress_hook(self, job: PlaylistJob, item, data: dict):
        status = data.get("status")
        if status == "downloading":
            filename = os.path.basename(data.get("filename", "")) or item.title
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            pct = downloaded / total * 100 if total else 0
            eta = data.get("eta")
            eta_text = f"ETA {eta}s" if eta is not None else ""

            now = time.time()
            if now - getattr(job, "_last_prog_log", 0.0) > 1.5:
                job._last_prog_log = now
                self.log(
                    job.playlist_title,
                    f"Download {filename[:38]}  {pct:5.1f}%  {fmt_speed(data.get('speed'))}  {eta_text}",
                    "PROGRESS",
                )
            self.after(0, lambda fn=filename[:52], pt=job.playlist_title: self.lbl_current.config(text=f"{pt}: {fn}"))
        elif status == "finished":
            self.log(job.playlist_title, f"Download complete: {item.title}; converting...", "SUCCESS")
        elif status == "error":
            self.log(job.playlist_title, f"Download error: {data.get('filename', item.title)}", "ERROR")

    def _pp_hook(self, job: PlaylistJob, item, data: dict):
        status = data.get("status")
        processor = data.get("postprocessor", "unknown")
        labels = {
            "ExtractAudio": "Extracting audio with FFmpeg",
            "Metadata": "Writing metadata tags",
            "ThumbnailsConvertor": "Converting artwork to JPEG",
            "EmbedThumbnail": "Embedding artwork into file",
        }
        label = labels.get(processor, f"Post-processing: {processor}")

        if status == "started":
            self.log(job.playlist_title, f"{label}...", "INFO")
            if processor == "ExtractAudio":
                duration = item.duration or float((data.get("info_dict") or {}).get("duration") or 0)
                item.duration = duration
                if duration:
                    output_dur = duration / job.speed if job.speed > 0 else duration
                    speed_note = f" output about {fmt_duration(output_dur)}" if job.speed != 1.0 else ""
                    self.log(
                        job.playlist_title,
                        f"Source: {fmt_duration(duration)};{speed_note} reading FFmpeg stderr progress...",
                        "INFO",
                    )
                else:
                    self.log(job.playlist_title, "Duration unknown; showing FFmpeg elapsed time.", "INFO")
                self.after(0, lambda it=item, pt=job.playlist_title: self.lbl_current.config(
                    text=f"FFmpeg: {pt}: {it.title[:46]}"))
        elif status == "finished" and processor == "ExtractAudio":
            self.log(job.playlist_title, "Audio extraction complete", "SUCCESS")

    def _ffmpeg_progress_hook(self, job: PlaylistJob, item, progress):
        now = time.time()
        if now - getattr(job, "_last_ffmpeg_prog_log", 0.0) < 1.5:
            return
        job._last_ffmpeg_prog_log = now

        expected = item.duration / job.speed if item.duration and job.speed > 0 else 0
        pct_text = f"  {min(progress.time_seconds / expected * 100, 99):.0f}%" if expected else ""
        speed_text = f"  {progress.speed}" if progress.speed else ""
        size_text = f"  {progress.size}" if progress.size else ""
        self.log(
            job.playlist_title,
            f"FFmpeg {fmt_duration(progress.time_seconds)}{pct_text}{speed_text}{size_text}",
            "PROGRESS",
        )

    def _update_job_progress(self, job: PlaylistJob):
        pct = job.completed_videos / job.total_videos * 100 if job.total_videos else 0
        self.after(0, lambda j=job, p=pct: (
            self.job_progress_bars[j.job_id].configure(value=p),
            self.job_progress_labels[j.job_id].config(
                text=f"#{j.job_id + 1} {j.playlist_title[:38]}  {j.completed_videos}/{j.total_videos}"
            ),
        ))

    def _finish_job_ui(self, job: PlaylistJob):
        elapsed = summarize_elapsed(job)
        has_error = job.failed_videos or job.status == "error"
        level = "WARNING" if has_error else "SUCCESS"
        self.log(
            job.playlist_title,
            f"Done {job.completed_videos}/{job.total_videos} files ({job.failed_videos} failed) elapsed {elapsed}",
            level,
        )
        if getattr(job, "output_folder", ""):
            self.log(job.playlist_title, f"-> {job.output_folder}", level)

        def finish_bar(j=job):
            bar = self.job_progress_bars.get(j.job_id)
            label = self.job_progress_labels.get(j.job_id)
            if bar:
                bar.configure(
                    style="Horizontal.TProgressbar" if (j.failed_videos or j.status == "error") else "Green.Horizontal.TProgressbar",
                    value=(j.completed_videos / j.total_videos * 100 if j.total_videos else 100),
                )
            if label:
                label.config(
                    fg=Theme.YELLOW if (j.failed_videos or j.status == "error") else Theme.GREEN,
                    text=f"#{j.job_id + 1} {'ERR' if (j.failed_videos or j.status == 'error') else 'OK'} "
                         f"{j.playlist_title[:28]}  {j.completed_videos}/{j.total_videos}",
                )

        self.after(0, finish_bar)

    def _update_overall(self):
        total = sum(job.total_videos for job in self.jobs)
        done = sum(job.completed_videos for job in self.jobs)
        if total > 0:
            pct = done / total * 100
            self.after(0, lambda: self.pb_overall.configure(value=pct))
            self.after(0, lambda: self.lbl_progress_count.config(text=f"{done} / {total} files"))

    def _on_all_finished(self):
        self.is_running = False
        self._set_system_sleep_state(prevent=False)

        cancelled = sum(1 for job in self.jobs if job.status == "cancelled")
        errors = sum(1 for job in self.jobs if job.status == "error")
        completed = sum(1 for job in self.jobs if job.status == "completed")
        total_done = sum(job.completed_videos for job in self.jobs)

        self.after(0, lambda: self.btn_start.config(state="normal"))
        self.after(0, lambda: self.btn_stop.config(state="disabled"))
        self.after(0, lambda: self.lbl_current.config(text="Idle"))

        if cancelled:
            self.after(0, lambda: self.lbl_badge.config(text="CANCELLED", fg=Theme.YELLOW))
            self.log("SYSTEM", "Downloads cancelled.", "WARNING")
        elif errors:
            self.after(0, lambda: self.lbl_badge.config(text=f"DONE ({errors} error{'s' if errors > 1 else ''})", fg=Theme.YELLOW))
            self.log(
                "SYSTEM",
                f"Finished: {completed} job(s) OK, {errors} with errors, {total_done} files total.",
                "WARNING",
            )
        else:
            self.after(0, lambda: self.lbl_badge.config(text="ALL DONE", fg=Theme.GREEN))
            self.log("SYSTEM", f"All done. {completed} job(s), {total_done} files.", "SUCCESS")
            self.log("SYSTEM", f"Files saved to: {self.var_output_dir.get()}", "SUCCESS")

            when_done = getattr(self, "var_when_done", None)
            if when_done and when_done.get() != "Do nothing":
                self._execute_power_action(when_done.get())

    def _set_system_sleep_state(self, prevent: bool):
        import platform

        if platform.system() == "Windows":
            import ctypes

            es_continuous = 0x80000000
            es_system_required = 0x00000001
            if prevent:
                ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(es_continuous)

    def _execute_power_action(self, action: str):
        import platform

        if platform.system() != "Windows":
            self.log("SYSTEM", "Post-completion tasks are only supported on Windows.", "ERROR")
            return

        self.log("SYSTEM", f"Executing post-completion task: {action}", "WARNING")
        time.sleep(2)

        commands = {
            "Shutdown": r"%windir%\System32\shutdown.exe -s -t 15",
            "Reboot": r"%windir%\System32\shutdown.exe -r -t 15",
            "Logoff": r"%windir%\System32\shutdown.exe -l -t 15",
            "Sleep": r"%windir%\System32\rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "Hibernate": r"%windir%\System32\rundll32.exe powrprof.dll,SetSuspendState Hibernate",
        }
        command = commands.get(action)
        if command:
            os.system(command)
        else:
            self.log("SYSTEM", f"Unknown action: {action}", "ERROR")
