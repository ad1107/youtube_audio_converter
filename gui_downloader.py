import os
import time
import threading
import queue
import subprocess
import shutil
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yt_dlp
    from yt_dlp import YoutubeDL
except ImportError:
    yt_dlp = None
    YoutubeDL = None

from models_utils import (
    PlaylistJob, _fmt_duration, _parse_ffmpeg_progress,
    FORMATS, QUALITIES, Theme, LOG_COLOURS,
    get_ffmpeg_path, YTLogger,
)


# ── URL type detection ────────────────────────────────────────────────────────

def _detect_no_playlist(url: str) -> bool:
    """
    Return True  → treat as single video  (noplaylist=True in yt-dlp)
    Return False → treat as full playlist (noplaylist=False in yt-dlp)

    A URL is treated as a playlist when:
      • path is exactly /playlist          (e.g. youtube.com/playlist?list=PL…)
      • has a `list=` query parameter      (e.g. watch?v=X&list=PL…)
    Everything else is a single video.
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if parsed.path.rstrip("/") == "/playlist":
            return False
        if "list" in params:
            return False
    except Exception:
        pass
    return True


def _url_kind_label(url: str) -> str:
    return "single video" if _detect_no_playlist(url) else "playlist"


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
            self.log_text.insert("end", f"[{source[:22]:<22s}] ", "SRC")
        self.log_text.insert("end", f"{message}\n", lvl_tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files","*.txt"),("All","*.*")],
            initialfile=f"audiobook_log_{datetime.now():%Y%m%d_%H%M%S}.txt")
        if path:
            Path(path).write_text(self.log_text.get("1.0","end"), encoding="utf-8")
            self.log("SYSTEM", f"Log saved → {path}", "SUCCESS")

    # ── Download Control ──────────────────────────────────────────────────────

    def _start(self):
        if yt_dlp is None:
            messagebox.showerror("Missing yt-dlp","yt-dlp not installed.\npip install yt-dlp")
            return
        if not get_ffmpeg_path():
            messagebox.showerror("Missing FFmpeg",
                                  "FFmpeg not found.\nhttps://ffmpeg.org/download.html")
            return
        urls = [e.get().strip() for _, e in self.playlist_row_widgets if e.get().strip()]
        if not urls:
            messagebox.showwarning("No URLs","Please add at least one YouTube URL.")
            return
        out_dir = self.var_output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("No Output","Please set an output folder.")
            return

        fmt     = FORMATS.get(self.var_format.get(),  "m4a")
        quality = QUALITIES.get(self.var_quality.get(), "0")
        os.makedirs(out_dir, exist_ok=True)
        self.cancel_flag.clear()
        self.is_running = True
        
        # Prevent sleep while downloading
        self._set_system_sleep_state(prevent=True)

        speed = float(self.var_speed.get() or 1.0)

        self.jobs = [
            PlaylistJob(url=url, output_dir=out_dir, fmt=fmt, quality=quality, speed=speed, job_id=i)
            for i, url in enumerate(urls)]

        self.pb_overall["value"] = 0
        self.lbl_progress_count.config(text="0 / ? files")
        self.lbl_current.config(text="Starting…")
        for w in self.playlist_progress_frame.winfo_children():
            w.destroy()

        self.job_progress_bars   = {}
        self.job_progress_labels = {}
        for job in self.jobs:
            jf  = tk.Frame(self.playlist_progress_frame, bg=Theme.BG2)
            jf.pack(fill="x", pady=2)
            lbl = tk.Label(jf, text=f"#{job.job_id+1} Fetching…", bg=Theme.BG2,
                           fg=Theme.MUTED, font=("Courier New", 8), anchor="w")
            lbl.pack(fill="x")
            pb  = ttk.Progressbar(jf, mode="indeterminate",
                                   style="Horizontal.TProgressbar")
            pb.pack(fill="x")
            pb.start(15)
            self.job_progress_bars[job.job_id]   = pb
            self.job_progress_labels[job.job_id] = lbl

        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_badge.config(text="● DOWNLOADING", fg=Theme.YELLOW)
        threading.Thread(target=self._run_all, daemon=True).start()

    def _stop(self):
        self.cancel_flag.set()
        self.log("SYSTEM","Stop requested – finishing current file then halting…","WARNING")
        self.btn_stop.config(state="disabled")
        self.lbl_badge.config(text="● STOPPING…", fg=Theme.YELLOW)

    def _run_all(self):
        n = self.var_concurrent.get()
        self.log("SYSTEM", f"Launching {len(self.jobs)} job(s) — {n} concurrent", "INFO")
        with ThreadPoolExecutor(max_workers=n) as ex:
            fmap = {ex.submit(self._download_job, job): job for job in self.jobs}
            for fut in as_completed(fmap):
                job = fmap[fut]
                try:
                    fut.result()
                except Exception as e:
                    if not self.cancel_flag.is_set():
                        self.log(job.playlist_title, f"Unhandled error: {e}", "ERROR")
                        job.status = "error"
        self._on_all_finished()

    # ── Single Job Download ────────────────────────────────────────────────────

    def _download_job(self, job: PlaylistJob):
        if self.cancel_flag.is_set():
            job.status = "cancelled"; return

        job.status     = "running"
        job.start_time = time.time()

        # ── Detect URL type ───────────────────────────────────────────────────
        no_playlist = _detect_no_playlist(job.url)
        kind_label  = _url_kind_label(job.url)

        # ── Output template ───────────────────────────────────────────────────
        filename_tmpl = ("%(playlist_index)02d - %(title)s.%(ext)s"
                         if self.var_track_num.get() else "%(title)s.%(ext)s")
        outtmpl = os.path.join(job.output_dir, "%(playlist_title,playlist)s", filename_tmpl)

        # ── Post-processors ───────────────────────────────────────────────────
        is_he_aac = job.quality.startswith("he_")
        is_lossless = job.fmt in ["flac", "wav", "aiff", "alac"]

        pp_extract = {"key": "FFmpegExtractAudio", "preferredcodec": job.fmt}
        if not is_he_aac and not is_lossless:
            pp_extract["preferredquality"] = job.quality

        postprocessors = [pp_extract]
        if self.var_metadata.get():
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        if self.var_thumbnail.get():
            postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
            postprocessors.append({"key": "EmbedThumbnail"})

        # ── postprocessor_args ────────────────────────────────────────────────
        #
        # KEY FORMAT (yt-dlp documented):
        #   "FFmpegExtractAudio+ffmpeg_o"   — output-side args for FFmpegExtractAudioPP
        #   "FFmpegThumbnailsConvertor+ffmpeg_o" — output-side args for thumbnail PP
        #
        # The "+ffmpeg_o" suffix tells yt-dlp to inject these AFTER the -i flag.
        # The class-name prefix WITHOUT the trailing "PP" is what yt-dlp uses as
        # the key (confirmed in yt-dlp README postprocessor-args examples).
        #
        # NOTE: We intentionally do NOT pass -progress here.  The -progress file
        # approach proved unreliable (key mismatches, Windows path quoting, yt-dlp
        # version differences).  Progress is now tracked by polling the growing
        # output file size — see _start_ffmpeg_monitor().
        #
        pp_args: dict = {}

        af = None
        if job.speed != 1.0:
            # atempo range is [0.5, 100.0]. Chain two filters for < 0.5×.
            if job.speed < 0.5:
                af = f"atempo=0.5,atempo={job.speed / 0.5:.4f}"
            else:
                af = f"atempo={job.speed}"
            
        if is_he_aac:
            bitrate = job.quality.split("_")[1] + "k"
            extract_args = ["-c:a", "libfdk_aac", "-profile:a", "aac_he", "-b:a", bitrate, "-ac", "1", "-ar", "44100"]
            if af:
                extract_args.extend(["-af", af])
            pp_args["extractaudio+ffmpeg_o"] = extract_args
        elif af:
            # Identify appropriate audio encoder based on format
            encoder_map = {
                "m4a": "aac",
                "mp3": "libmp3lame",
                "flac": "flac",
                "wav": "pcm_s16le",
                "aiff": "pcm_s16be",
                "alac": "alac"
            }
            enc = encoder_map.get(job.fmt, "aac")
            
            # We don't overwrite if yt-dlp has 'extractaudio+ffmpeg_o' wait, we do:
            pp_args["extractaudio+ffmpeg_o"] = ["-c:a", enc, "-af", af]

        if self.var_thumbnail.get() and self.var_crop_thumb.get():
            crop_vf = "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"
            pp_args["thumbnailsconvertor+ffmpeg_o"] = ["-c:v", "mjpeg", "-vf", crop_vf]

        log_file_path = os.path.join(job.output_dir, f"ffmpeg_log_{job.job_id}.txt").replace("\\", "/")
        if "extractaudio+ffmpeg_o" not in pp_args:
            pp_args["extractaudio+ffmpeg_o"] = []
        pp_args["extractaudio+ffmpeg_o"].extend(["-progress", f"file:{log_file_path}"])

        # ── YTLogger with destination-capture callback ────────────────────────
        #
        # cb_extract_dest fires unconditionally (regardless of verbose setting)
        # whenever yt-dlp logs "[ExtractAudio] Destination: <path>".  We store
        # that path on the job so the progress monitor knows which file to watch.
        #
        def _on_extract_dest(path: str, j: PlaylistJob = job):
            j._ffmpeg_output_path = path
            # Don't overwrite conv_start if already set (duplicate hook guard)
            if j._ffmpeg_conv_start == 0.0:
                j._ffmpeg_conv_start = time.time()

        # Ensure we capture ffmpeg command line output to debug it
        def _debug_hook(msg, j=job):
            if "ffmpeg command line:" in msg:
                self.log(j.playlist_title, f"FFmpeg Executing: {msg}", "DEBUG")
                
        ydl_opts = {
            "format":                        "bestaudio/best",
            "outtmpl":                       outtmpl,
            "postprocessors":                postprocessors,
            "postprocessor_args":            pp_args,
            "writethumbnail":                self.var_thumbnail.get(),
            "noplaylist":                    no_playlist,
            "ignoreerrors":                  True,
            "no_warnings":                   False,
            "quiet":                         True,
            "color":                         "no_color",
            "nooverwrites":                  self.var_skip_existing.get(),
            "progress_hooks":                [lambda d, j=job: self._progress_hook(d, j)],
            "postprocessor_hooks":           [lambda d, j=job: self._pp_hook(d, j)],
            "concurrent_fragment_downloads": 4,
            "logger": YTLogger(
                cb_info  = None,
                cb_warn  = lambda m, j=job: (None if "JavaScript runtime" in m
                                             else self.log(j.playlist_title, m, "WARNING")),
                cb_err   = lambda m, j=job: self.log(j.playlist_title, m, "ERROR"),
                cb_debug = _debug_hook,
                cb_extract_dest = _on_extract_dest,
            ),
        }

        if self.var_track_num.get() and self.var_metadata.get():
            ydl_opts["parse_metadata"] = ["%(playlist_index)s:%(track_number)s"]

        self.log(job.url[:60],
                 f"Auto-detected as {kind_label} — fetching metadata…", "INFO")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                # Phase 1 — info only
                try:
                    info = ydl.extract_info(job.url, download=False)
                except Exception as e:
                    self.log(job.url[:60], f"Failed to fetch info: {e}", "ERROR")
                    job.status = "error"; job.error_msg = str(e); return

                if info is None:
                    self.log(job.url[:60],
                             "Could not retrieve info (private/unavailable?)", "ERROR")
                    job.status = "error"; return

                if "entries" in info:
                    job.playlist_title = info.get("title") or "Unknown Playlist"
                    entries            = [e for e in (info.get("entries") or []) if e]
                    job.total_videos   = len(entries)
                else:
                    job.playlist_title = info.get("title") or "Single Video"
                    job.total_videos   = 1

                job.output_folder = os.path.join(job.output_dir, job.playlist_title)
                speed_str = f"  ·  {job.speed}× speed" if job.speed != 1.0 else ""
                self.log(job.playlist_title,
                         f"Found {job.total_videos} video(s) → {job.fmt.upper()} @ {job.quality}{speed_str}",
                         "INFO")
                self.after(0, lambda j=job: self.job_progress_labels[j.job_id].config(
                    text=f"#{j.job_id+1} {j.playlist_title[:30]} — 0/{j.total_videos}"))
                self.after(0, lambda j=job: self.job_progress_bars[j.job_id].stop())
                self.after(0, lambda j=job: self.job_progress_bars[j.job_id].configure(
                    mode="determinate", value=0))

                if self.cancel_flag.is_set():
                    job.status = "cancelled"; return

                # Phase 2 — download
                self.log(job.playlist_title, f"Starting download → {job.output_folder}", "INFO")
                ydl.download([job.url])

            job.status   = "completed"
            job.end_time = time.time()
            mins, secs   = divmod(int(job.end_time - job.start_time), 60)
            self.log(job.playlist_title,
                     (f"✓ Done  {job.completed_videos}/{job.total_videos} files  "
                      f"({job.failed_videos} failed)  elapsed {mins}m{secs:02d}s"),
                     "SUCCESS")
            self.log(job.playlist_title, f"  → {job.output_folder}", "SUCCESS")

            def _finish_bar(j=job):
                pb  = self.job_progress_bars.get(j.job_id)
                lbl = self.job_progress_labels.get(j.job_id)
                if pb:  pb.configure(style="Green.Horizontal.TProgressbar", value=100)
                if lbl: lbl.config(fg=Theme.GREEN,
                                    text=(f"#{j.job_id+1} ✓ {j.playlist_title[:28]}  "
                                          f"{j.completed_videos}/{j.total_videos}"))
            self.after(0, _finish_bar)

        except yt_dlp.utils.DownloadError as de:
            job.status = "cancelled" if self.cancel_flag.is_set() else "error"
            if job.status == "error":
                job.error_msg = str(de)
                self.log(job.playlist_title, f"Download error: {de}", "ERROR")
        except Exception as e:
            job.status    = "error"
            job.error_msg = str(e)
            self.log(job.playlist_title, f"Unexpected error: {e}", "ERROR")
        finally:
            self._stop_ffmpeg_monitor(job)

    # ── Download / Post-process Hooks ─────────────────────────────────────────

    def _progress_hook(self, d: dict, job: PlaylistJob):
        """Called by yt-dlp during the network download phase."""
        if self.cancel_flag.is_set():
            raise yt_dlp.utils.DownloadError("Cancelled by user")

        status = d.get("status")

        if status == "downloading":
            fname     = os.path.basename(d.get("filename", ""))
            speed     = d.get("speed") or 0
            eta       = d.get("eta")
            dl_bytes  = d.get("downloaded_bytes", 0)
            total     = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct       = (dl_bytes / total * 100) if total else 0
            speed_mb  = speed / 1024 / 1024
            speed_str = f"{speed_mb:.1f} MB/s" if speed else "…"
            eta_str   = f"ETA {eta}s"           if eta is not None else ""

            now = time.time()
            if now - job._last_prog_log > 1.5:
                job._last_prog_log = now
                self.log(job.playlist_title,
                         f"↓ {fname[:38]}  {pct:5.1f}%  {speed_str}  {eta_str}",
                         "PROGRESS")
            self.after(0, lambda fn=fname[:52], pt=job.playlist_title:
                       self.lbl_current.config(text=f"{pt}: {fn}"))

        elif status == "finished":
            fname = os.path.basename(d.get("filename", ""))
            self.log(job.playlist_title,
                     f"⬇ Download complete: {fname} — handing off to FFmpeg…", "SUCCESS")
            job.completed_videos += 1
            self._update_overall()
            if job.total_videos > 0:
                pct = job.completed_videos / job.total_videos * 100
                self.after(0, lambda j=job, p=pct: (
                    self.job_progress_bars[j.job_id].configure(value=p),
                    self.job_progress_labels[j.job_id].config(
                        text=f"#{j.job_id+1} {j.playlist_title[:28]}  "
                             f"{j.completed_videos}/{j.total_videos}")))

        elif status == "error":
            job.failed_videos += 1
            self.log(job.playlist_title, f"Download error: {d.get('filename','?')}", "ERROR")

    def _pp_hook(self, d: dict, job: PlaylistJob):
        """
        Called by yt-dlp when a post-processor starts or finishes.

        Duplicate-firing guard
        ──────────────────────
        Some yt-dlp versions (and some URL/playlist combinations) call this
        hook twice in quick succession for the same "ExtractAudio started"
        event.  We guard against that by recording the wall-clock time of the
        first "started" call and ignoring any second call that arrives within
        3 seconds.  This prevents starting two competing monitor threads for
        the same ffmpeg invocation, which would flood the log.
        """
        status = d.get("status")
        pp     = d.get("postprocessor", "unknown")

        PP_LABELS = {
            "ExtractAudio":       "Extracting audio with FFmpeg",
            "Metadata":           "Writing metadata tags",
            "ThumbnailsConvertor":"Converting artwork to JPEG",
            "EmbedThumbnail":     "Embedding artwork into file",
        }
        label = PP_LABELS.get(pp, f"Post-processing: {pp}")

        if status == "started":
            self.log(job.playlist_title, f"↻ {label}…", "INFO")

            if pp == "ExtractAudio":
                now = time.time()

                # ── Duplicate-fire guard ─────────────────────────────────────
                # If we already started a monitor for this video within the last
                # 3 seconds, skip — it's a duplicate hook call from yt-dlp.
                last_start = getattr(job, "_extract_audio_hook_ts", 0.0)
                if now - last_start < 3.0 and last_start > 0:
                    return
                job._extract_audio_hook_ts = now
                # ─────────────────────────────────────────────────────────────

                info_dict = d.get("info_dict") or {}
                duration  = float(info_dict.get("duration") or 0)
                title     = info_dict.get("title", "")

                if duration:
                    output_dur = duration / job.speed if job.speed > 0 else duration
                    speed_note = (f"  ·  output ≈ {_fmt_duration(output_dur)}"
                                  if job.speed != 1.0 else "")
                    self.log(job.playlist_title,
                             f"   Source: {_fmt_duration(duration)}"
                             f"  (~{duration/60:.1f} min){speed_note} — monitoring FFmpeg…",
                             "INFO")
                else:
                    self.log(job.playlist_title,
                             "   Duration unknown — showing elapsed time + file size", "INFO")

                # Reset per-video state
                job._current_video_duration = duration
                job._ffmpeg_output_path     = ""    # will be filled by _on_extract_dest
                job._ffmpeg_conv_start      = now   # fallback start time (overwritten
                                                    # by _on_extract_dest when the
                                                    # Destination line arrives)
                self._start_ffmpeg_monitor(job)

                self.after(0, lambda t=title, pt=job.playlist_title:
                           self.lbl_current.config(text=f"FFmpeg ▸ {pt}: {t[:46]}"))

        elif status == "finished":
            if pp == "ExtractAudio":
                self._stop_ffmpeg_monitor(job)
                # Ensure the final progress line displays 100% since extraction completed.
                try:
                    path = job._ffmpeg_output_path
                    if path and os.path.exists(path):
                        size_mb = os.path.getsize(path) / (1024 * 1024)
                        elapsed = time.time() - getattr(job, "_ffmpeg_conv_start", time.time())
                        self.log(job.playlist_title, f"  🔧 FFmpeg done {_fmt_duration(elapsed)}  {size_mb:.1f} MB  (100%)", "PROGRESS")
                    else:
                        self.log(job.playlist_title, f"  🔧 FFmpeg done", "PROGRESS")
                except Exception:
                    pass
                self.log(job.playlist_title, "✓ Audio extraction complete", "SUCCESS")

    # ── FFmpeg Progress Monitor ───────────────────────────────────────────────

    def _start_ffmpeg_monitor(self, job: PlaylistJob):
        """
        Polls the growing output file (the .m4a / .mp3 / etc. that ffmpeg is
        writing) every 0.5 s and emits a PROGRESS log line every ~2 s.

        Why file-size instead of -progress pipe
        ────────────────────────────────────────
        The -progress file approach requires yt-dlp to correctly map our
        postprocessor_args key to the right ffmpeg invocation.  That mapping
        is yt-dlp-version-sensitive and broke silently (wrong key → args
        ignored → ffmpeg never writes to the file → monitor logs nothing).

        Polling the output file is unconditional: ffmpeg always writes the
        output, we always know the path (captured from the "[ExtractAudio]
        Destination:" log line via YTLogger.cb_extract_dest), and os.path
        .getsize() is available everywhere.

        Progress estimation
        ───────────────────
        We know:  duration (seconds), quality/bitrate (kbps), speed factor.
        Estimated output bytes = kbps × 1000/8 × (duration / speed).
        This is accurate for CBR modes.  For VBR ("0") we assume 192 kbps.
        """
        job._ffmpeg_poll_stop.clear()
        job._ffmpeg_poll_gen += 1
        my_gen = job._ffmpeg_poll_gen
        
        duration = job._current_video_duration
        log_file = os.path.join(job.output_dir, f"ffmpeg_log_{job.job_id}.txt")

        def _poll(stop: threading.Event, j: PlaylistJob, gen: int, log_path: str):
            last_logged = 0.0
            while not stop.is_set() and j._ffmpeg_poll_gen == gen:
                try:
                    data = _parse_ffmpeg_progress(log_path)
                    if data:
                        out_time_us = data.get("out_time_us", "0")
                        try:
                            # ffmpeg out_time_us can be "N/A"
                            out_time = float(out_time_us) / 1000000.0
                        except ValueError:
                            out_time = 0.0
                            
                        now = time.time()
                        if now - last_logged >= 2.0 and out_time > 0:
                            last_logged = now
                            elapsed_str = _fmt_duration(out_time)
                            
                            if duration > 0:
                                expected_out_duration = duration / j.speed if j.speed > 0 else duration
                                pct = min((out_time / expected_out_duration) * 100, 99.0)
                                msg = f"  🔧 FFmpeg  {elapsed_str}  ({pct:.0f}%)"
                            else:
                                msg = f"  🔧 FFmpeg  {elapsed_str}"
                            self.log(j.playlist_title, msg, "PROGRESS")
                except Exception:
                    pass
                time.sleep(0.5)
            
            # cleanup
            if os.path.exists(log_path):
                try: os.unlink(log_path)
                except Exception: pass

        threading.Thread(
            target=_poll,
            args=(job._ffmpeg_poll_stop, job, my_gen, log_file),
            daemon=True,
            name=f"ffprog-job{job.job_id}-gen{my_gen}",
        ).start()

    def _stop_ffmpeg_monitor(self, job: PlaylistJob):
        job._ffmpeg_poll_stop.set()

    # ── Overall Progress ──────────────────────────────────────────────────────

    def _update_overall(self):
        total = sum(j.total_videos     for j in self.jobs)
        done  = sum(j.completed_videos for j in self.jobs)
        if total > 0:
            pct = done / total * 100
            self.after(0, lambda: self.pb_overall.configure(value=pct))
            self.after(0, lambda: self.lbl_progress_count.config(
                text=f"{done} / {total} files"))

    # ── Finish ────────────────────────────────────────────────────────────────

    def _on_all_finished(self):
        self.is_running = False
        
        # Allow sleep again
        self._set_system_sleep_state(prevent=False)

        cancelled  = sum(1 for j in self.jobs if j.status == "cancelled")
        errors     = sum(1 for j in self.jobs if j.status == "error")
        completed  = sum(1 for j in self.jobs if j.status == "completed")
        total_done = sum(j.completed_videos for j in self.jobs)

        self.after(0, lambda: self.btn_start.config(state="normal"))
        self.after(0, lambda: self.btn_stop.config(state="disabled"))
        self.after(0, lambda: self.lbl_current.config(text="Idle"))

        if cancelled:
            self.after(0, lambda: self.lbl_badge.config(text="● CANCELLED", fg=Theme.YELLOW))
            self.log("SYSTEM", "Downloads cancelled.", "WARNING")
        elif errors:
            badge = f"● DONE ({errors} error{'s' if errors>1 else ''})"
            self.after(0, lambda b=badge: self.lbl_badge.config(text=b, fg=Theme.YELLOW))
            self.log("SYSTEM",
                     f"Finished — {completed} job(s) OK, {errors} with errors, "
                     f"{total_done} files total.", "WARNING")
        else:
            self.after(0, lambda: self.lbl_badge.config(text="● ALL DONE ✓", fg=Theme.GREEN))
            self.log("SYSTEM", f"All done! {completed} job(s), {total_done} files.", "SUCCESS")
            self.log("SYSTEM", f"Files saved to: {self.var_output_dir.get()}", "SUCCESS")
            self.log("SYSTEM", "→ Apple Music:  File ▸ Add Folder to Library", "INFO")
            self.log("SYSTEM", "→ 3uTools:       Files ▸ Import to Device",    "INFO")

            # Post completion hook
            when_done = getattr(self, "var_when_done", None)
            if when_done and when_done.get() != "Do nothing":
                self._execute_power_action(when_done.get())

    def _set_system_sleep_state(self, prevent: bool):
        """Prevents the system from sleeping using Windows ctypes."""
        import platform # type: ignore
        if platform.system() == "Windows":
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            if prevent:
                # Prevent sleep
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            else:
                # Allow sleep
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    def _execute_power_action(self, action: str):
        import platform, os, time
        if platform.system() != "Windows":
            self.log("SYSTEM", "Post-completion tasks are only supported on Windows.", "ERROR")
            return

        self.log("SYSTEM", f"Executing post-completion task: {action}", "WARNING")
        time.sleep(2)

        commands = {
            "Shutdown": r"%windir%\System32\shutdown.exe -s -t 15",
            "Reboot":   r"%windir%\System32\shutdown.exe -r -t 15",
            "Logoff":   r"%windir%\System32\shutdown.exe -l -t 15",
            "Sleep":    r"%windir%\System32\rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "Hibernate":r"%windir%\System32\rundll32.exe powrprof.dll,SetSuspendState Hibernate",
        }

        cmd = commands.get(action)
        if cmd:
            os.system(cmd)
        else:
            self.log("SYSTEM", f"Unknown action: {action}", "ERROR")