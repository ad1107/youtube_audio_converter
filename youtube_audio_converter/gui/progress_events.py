import os
import time

from youtube_audio_converter.core.download import summarize_elapsed
from youtube_audio_converter.core.formats import supports_audio_filters
from youtube_audio_converter.core.formatting import fmt_duration, fmt_speed
from youtube_audio_converter.core.postprocessor_labels import (
    FINALIZING_POSTPROCESSORS,
    PROGRESS_POSTPROCESSORS,
    postprocessor_label,
)


class ProgressEventsMixin:
    def _on_job_metadata(self, job, title: str, total: int, output_folder: str):
        self.signals.current_text.emit(f"{job.playlist_title}: queued {job.total_videos} item(s)")
        self._emit_job_state(job, status=f"0/{job.total_videos}")
        self._emit_overall()

    def _on_item_queued(self, job, item, index: int):
        self.signals.current_text.emit(f"{job.playlist_title}: queued {item.title[:52]}")
        self._emit_item_state(job, item, "download", 0, "Queued", f"Source: {item.url}", active=False, force=True)

    def _on_item_started(self, job, item, index: int):
        self.signals.current_text.emit(f"{job.playlist_title}: {item.title[:52]}")
        self._emit_item_state(job, item, "download", 0, "Downloading 0%", f"Source: {item.url}", active=True, force=True)

    def _on_item_skipped(self, job, item, path: str):
        self._emit_overall()
        self._emit_item_state(job, item, "skipped", 100, "Skipped", f"Existing file: {path}", active=False, tone="skipped", force=True)
        self.signals.current_text.emit(f"Skipped existing: {item.title[:52]}")

    def _on_item_done(self, job, item, path: str):
        self._emit_overall()
        self._emit_item_state(job, item, "done", 100, "Done", f"Saved: {path}", active=False, tone="done", force=True)
        self.log(job.playlist_title, f"Saved: {item.title}", "SUCCESS")

    def _on_item_failed(self, job, item, failure):
        failed = failure.as_dict() if hasattr(failure, "as_dict") else dict(failure)
        with self.failed_items_lock:
            self.failed_items.append(failed)
        if item is not None:
            self._emit_item_state(job, item, "failed", 100, "Failed", f"Source: {item.url}", active=False, tone="failed", force=True)
        self._emit_overall()

    def _progress_hook(self, job, item, data: dict):
        status = data.get("status")
        if status == "downloading":
            self._handle_download_progress(job, item, data)
        elif status == "finished":
            if getattr(item, "_download_finished_logged", False):
                return
            item._download_finished_logged = True
            self.log(job.playlist_title, f"Download complete: {item.title}; post-processing...", "SUCCESS")
            self._emit_item_state(job, item, "download", 100, "Downloaded", f"Downloaded source: {item.url}", force=True)
        elif status == "error":
            self.log(job.playlist_title, f"Download error: {data.get('filename', item.title)}", "ERROR")
            self._emit_item_state(job, item, "failed", 100, "Download failed", f"Source: {item.url}", active=False, tone="failed", force=True)

    def _handle_download_progress(self, job, item, data: dict):
        filename = os.path.basename(data.get("filename", "")) or item.title
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        downloaded = data.get("downloaded_bytes") or 0
        pct = downloaded / total * 100 if total else 0
        eta = data.get("eta")
        eta_text = f"ETA {eta}s" if eta is not None else ""
        detail = (
            f"Downloading: {filename} | {downloaded / 1024 / 1024:0.1f} MB"
            f"{f' / {total / 1024 / 1024:0.1f} MB' if total else ''}"
            f" | {fmt_speed(data.get('speed'))}"
            f"{f' | {eta_text}' if eta_text else ''} | Source: {item.url}"
        )
        self._emit_item_state(job, item, "download", pct, f"Downloading {pct:0.0f}%", detail)

        now = time.time()
        if now - getattr(job, "_last_prog_log", 0.0) > 1.5:
            job._last_prog_log = now
            self.log(job.playlist_title, f"Download {filename[:38]}  {pct:5.1f}%  {fmt_speed(data.get('speed'))}  {eta_text}", "PROGRESS")
        self.signals.current_text.emit(f"{job.playlist_title}: {filename[:52]}")

    def _pp_hook(self, job, item, data: dict):
        status = data.get("status")
        processor = data.get("postprocessor", "unknown")
        label = postprocessor_label(processor)
        if self._already_seen_postprocessor(item, processor, status):
            return

        if status == "waiting":
            self.log(job.playlist_title, f"Waiting for convert slot: {label}...", "INFO")
            self._emit_item_state(job, item, "convert", 0, "Waiting convert slot", f"Waiting for convert slot: {label} | Output: {item.expected_path}", tone="convert", force=True)
        elif status == "started":
            self._handle_postprocessor_started(job, item, data, processor, label)
        elif status == "finished":
            self.log(job.playlist_title, f"{label} complete", "SUCCESS")
            if processor in FINALIZING_POSTPROCESSORS:
                self._emit_item_state(job, item, "convert", 100, "Finalizing", f"{label} complete: {item.expected_path}", tone="convert", force=True)

    def _already_seen_postprocessor(self, item, processor: str, status: str) -> bool:
        seen_attr = {"waiting": "_pp_waiting_seen", "started": "_pp_started_seen", "finished": "_pp_finished_seen"}.get(status)
        if not seen_attr:
            return False
        seen = getattr(item, seen_attr, set())
        if processor in seen:
            return True
        seen.add(processor)
        setattr(item, seen_attr, seen)
        return False

    def _handle_postprocessor_started(self, job, item, data: dict, processor: str, label: str):
        self.log(job.playlist_title, f"{label}...", "INFO")
        if processor in PROGRESS_POSTPROCESSORS:
            duration = item.duration or float((data.get("info_dict") or {}).get("duration") or 0)
            item.duration = duration
            if duration:
                output_dur = duration / job.speed if job.speed > 0 else duration
                speed_note = f" output about {fmt_duration(output_dur)}" if job.speed != 1.0 else ""
                self.log(job.playlist_title, f"Source: {fmt_duration(duration)};{speed_note} reading FFmpeg stderr progress...", "INFO")
            else:
                self.log(job.playlist_title, "Duration unknown; showing FFmpeg elapsed time.", "INFO")
            self.signals.current_text.emit(f"FFmpeg: {job.playlist_title}: {item.title[:46]}")
            self._emit_item_state(job, item, "convert", 0, "Converting", f"{label}: {item.expected_path}", tone="convert", force=True)
        elif processor in FINALIZING_POSTPROCESSORS:
            self._emit_item_state(job, item, "convert", 100, label, f"{label}: {item.expected_path}", tone="convert", force=True)
            self.signals.current_text.emit(f"{label}: {item.title[:52]}")

    def _ffmpeg_progress_hook(self, job, item, progress):
        if getattr(progress, "completed", False):
            self._emit_item_state(job, item, "convert", 100, "Finalizing", f"FFmpeg complete; finalizing output: {item.expected_path}", tone="convert", force=True)
            return

        effective_speed = job.speed if supports_audio_filters(job.fmt) else 1.0
        expected = item.duration / effective_speed if item.duration and effective_speed > 0 else 0
        percent = min(progress.time_seconds / expected * 100, 99) if expected else None
        status = f"Converting {percent:0.0f}%" if percent is not None else f"Converting {fmt_duration(progress.time_seconds)}"
        detail = (
            f"FFmpeg: elapsed {fmt_duration(progress.time_seconds)}"
            f"{f' | {percent:0.0f}%' if percent is not None else ''}"
            f"{f' | speed {progress.speed}' if progress.speed else ''}"
            f"{f' | size {progress.size}' if progress.size else ''}"
            f"{f' | bitrate {progress.bitrate}' if progress.bitrate else ''}"
            f" | Output: {item.expected_path}"
        )
        self._emit_item_state(job, item, "convert", percent, status, detail, tone="convert")
        self._log_ffmpeg_progress(job, item, progress, expected)

    def _log_ffmpeg_progress(self, job, item, progress, expected: float):
        now = time.time()
        if now - getattr(job, "_last_ffmpeg_prog_log", 0.0) < 1.5:
            return
        job._last_ffmpeg_prog_log = now
        pct_text = f"  {min(progress.time_seconds / expected * 100, 99):.0f}%" if expected else ""
        speed_text = f"  {progress.speed}" if progress.speed else ""
        size_text = f"  {progress.size}" if progress.size else ""
        self.log(job.playlist_title, f"FFmpeg {item.index:02d} - {item.title[:32]} {fmt_duration(progress.time_seconds)}{pct_text}{speed_text}{size_text}", "PROGRESS")

    def _finish_job_ui(self, job):
        elapsed = summarize_elapsed(job)
        has_error = job.failed_videos or job.status == "error"
        level = "WARNING" if has_error else "SUCCESS"
        self.log(job.playlist_title, f"Done {job.completed_videos}/{job.total_videos} files ({job.failed_videos} failed) elapsed {elapsed}", level)
        if getattr(job, "output_folder", ""):
            self.log(job.playlist_title, f"-> {job.output_folder}", level)
        self._emit_job_state(job, percent=100, status="Error" if has_error else "Done", tone="error" if has_error else "success")

    def _emit_job_state(self, job, percent: float | None = None, status: str | None = None, tone: str = "download"):
        total = job.total_videos or 0
        done = job.completed_videos + job.failed_videos
        value = percent if percent is not None else (done / total * 100 if total else 0)
        self.signals.job_state.emit(job.job_id, {"title": f"#{job.job_id + 1} {job.playlist_title[:90]}", "status": status or (f"{done}/{total}" if total else "Fetching"), "percent": value, "detail": getattr(job, "output_folder", "") or job.url, "tone": tone})

    def _emit_item_state(self, job, item, phase: str, percent: float | None, status: str, detail: str = "", active: bool = True, tone: str | None = None, force: bool = False):
        key = self._progress_key(job, item)
        if not force and not self._allow_item_update(key, percent, status):
            return
        self.signals.item_state.emit(key, {"job_id": job.job_id, "job_title": job.playlist_title, "item_index": item.index, "item_title": item.title[:90], "phase": phase, "percent": percent, "status": status, "detail": detail, "active": active, "tone": tone or phase})

    def _allow_item_update(self, key: str, percent: float | None, status: str) -> bool:
        now = time.monotonic()
        pct = None if percent is None else float(percent)
        with self._item_emit_lock:
            last = self._last_item_emit.get(key)
            if last:
                last_time, last_pct, last_status = last
                pct_delta = 100 if pct is None or last_pct is None else abs(pct - last_pct)
                if now - last_time < 0.18 and pct_delta < 1.0 and status == last_status:
                    return False
            self._last_item_emit[key] = (now, pct, status)
        return True

    def _emit_overall(self):
        total = sum(job.total_videos for job in self.jobs)
        done = sum(job.completed_videos + job.failed_videos for job in self.jobs)
        if total > 0:
            self.signals.overall_state.emit(done / total * 100, f"{done} / {total} files")
        for job in self.jobs:
            if job.total_videos:
                self._emit_job_state(job)

    def _progress_key(self, job, item) -> str:
        return f"{job.job_id}:{item.index}"

    def _progress_sort_key(self, key: str) -> tuple[int, int]:
        try:
            job_id, item_index = key.split(":", 1)
            return int(job_id), int(item_index)
        except (TypeError, ValueError):
            return 0, 0

    def _on_hide_inactive_tasks_changed(self, value: bool):
        self.progress_tree.set_hide_inactive(value)
