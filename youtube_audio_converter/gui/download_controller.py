import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6 import QtWidgets

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from youtube_audio_converter import dependencies
from youtube_audio_converter.core.download import run_download_job
from youtube_audio_converter.core.download_types import DownloadCallbacks, DownloadSettings, PlaylistJob
from youtube_audio_converter.core.formats import normalize_quality, quality_label_map
from youtube_audio_converter.core.runtime import DownloadRuntime


class DownloadControllerMixin:
    def _retry_errors(self):
        if self.is_running:
            QtWidgets.QMessageBox.information(self, "Retry Errors", "Wait for the current run to finish before retrying failed items.")
            return

        with self.failed_items_lock:
            failed = list(self.failed_items)
        urls = [item.get("url") if isinstance(item, dict) else getattr(item, "url", "") for item in failed]
        urls = [url for url in urls if url]
        if not urls:
            QtWidgets.QMessageBox.information(self, "Retry Errors", "No failed items to retry.")
            return

        self.url_table.setRowCount(0)
        for url in urls:
            self._add_playlist_row(url)

        with self.failed_items_lock:
            self.failed_items.clear()
        self.log("SYSTEM", f"Retrying {len(urls)} failed URL(s).", "INFO")
        self._start()

    def _start(self):
        cfg = self._validated_run_config()
        if cfg is None:
            return

        os.makedirs(cfg["output_dir"], exist_ok=True)
        self.cancel_flag.clear()
        self.is_running = True
        self._set_system_sleep_state(prevent=True)

        self.jobs = [
            PlaylistJob(
                url=url,
                output_dir=cfg["output_dir"],
                fmt=cfg["fmt"],
                quality=cfg["quality"],
                speed=cfg["speed"],
                volume=cfg["volume"],
                job_id=index,
                label=label,
            )
            for index, (label, url) in enumerate(cfg["sources"])
        ]
        self.run_config = cfg
        self._prepare_run_ui()
        threading.Thread(target=self._run_all, daemon=True).start()

    def _validated_run_config(self) -> dict | None:
        if yt_dlp is None:
            QtWidgets.QMessageBox.critical(self, "Missing yt-dlp", "yt-dlp not installed.\npip install yt-dlp")
            return None
        if not dependencies.get_ffmpeg_path():
            QtWidgets.QMessageBox.critical(self, "Missing FFmpeg", "FFmpeg not found.\nhttps://ffmpeg.org/download.html")
            return None

        sources = self._url_sources()
        if not sources:
            QtWidgets.QMessageBox.warning(self, "No URLs", "Please add at least one YouTube URL.")
            return None

        out_dir = self.output_dir_edit.text().strip()
        if not out_dir:
            QtWidgets.QMessageBox.warning(self, "No Output", "Please set an output folder.")
            return None

        cookiefile = self.cookiefile_edit.text().strip()
        if cookiefile and not os.path.isfile(cookiefile):
            QtWidgets.QMessageBox.critical(self, "Invalid Cookies File", f"Cookies file not found:\n{cookiefile}")
            return None

        fmt = self._selected_format()
        try:
            quality = normalize_quality(fmt, quality_label_map(fmt).get(self.quality_combo.currentText(), self.quality_combo.currentText()))
            speed = float(self.speed_combo.currentText() or 1.0)
            volume = float(self.volume_spin.value() or 1.0)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid Setting", str(exc))
            return None
        if speed <= 0 or volume <= 0:
            QtWidgets.QMessageBox.warning(self, "Invalid Audio Setting", "Speed and volume must be greater than 0.")
            return None

        return {
            "sources": sources,
            "output_dir": out_dir,
            "fmt": fmt,
            "quality": quality,
            "speed": speed,
            "volume": volume,
            "cookiefile": cookiefile,
            "cookies_browser": self.browser_combo.currentText().strip(),
            "use_deno": self.use_deno_check.isChecked(),
            "embed_thumbnail": self.thumbnail_check.isChecked(),
            "crop_thumbnail": self.crop_thumb_check.isChecked(),
            "embed_metadata": self.metadata_check.isChecked(),
            "track_num": self.track_num_check.isChecked(),
            "skip_existing": self.skip_existing_check.isChecked(),
            "suppress_js_warnings": self.suppress_js_check.isChecked(),
            "concurrent_downloads": max(1, self.concurrent_downloads_spin.value()),
            "concurrent_converts": max(1, self.concurrent_converts_spin.value()),
            "download_start_delay": max(0.0, self.download_start_delay_spin.value()),
        }

    def _selected_format(self) -> str:
        from .models import FORMATS

        return FORMATS.get(self.format_combo.currentText(), "m4a")

    def _prepare_run_ui(self):
        self.pb_overall.setValue(0)
        self.lbl_progress_count.setText("0 / ? files")
        self.lbl_current.setText("Starting...")
        self.progress_tree.reset()
        self.run_tabs.setCurrentWidget(self.progress_page)
        self._last_item_emit.clear()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_badge.setText("DOWNLOADING")
        self.lbl_badge.setObjectName("badgeRunning")
        self._refresh_badge_style()

    def _stop(self):
        self.cancel_flag.set()
        self.log("SYSTEM", "Stop requested; finishing current file then halting...", "WARNING")
        self.btn_stop.setEnabled(False)
        self.lbl_badge.setText("STOPPING...")
        self.lbl_badge.setObjectName("badgeRunning")
        self._refresh_badge_style()

    def _run_all(self):
        cfg = dict(self.run_config)
        download_slots = max(1, int(cfg.get("concurrent_downloads") or 1))
        convert_slots = max(1, int(cfg.get("concurrent_converts") or 1))
        start_delay = max(0.0, float(cfg.get("download_start_delay") or 0.0))
        self.download_runtime = DownloadRuntime(download_slots, convert_slots, start_delay)

        with self.failed_items_lock:
            self.failed_items.clear()

        self.log("SYSTEM", f"Launching {len(self.jobs)} source(s), DL {download_slots}, convert {convert_slots}, start gap {start_delay:g}s", "INFO")
        with ThreadPoolExecutor(max_workers=max(1, len(self.jobs))) as executor:
            future_map = {executor.submit(self._download_job, job, cfg): job for job in self.jobs}
            for future in as_completed(future_map):
                job = future_map[future]
                try:
                    future.result()
                except Exception as exc:
                    if not self.cancel_flag.is_set():
                        job.status = "error"
                        job.error_msg = str(exc)
                        self.log(job.playlist_title, f"Unhandled error: {exc}", "ERROR")
        self.signals.all_finished.emit()

    def _download_job(self, job: PlaylistJob, cfg: dict):
        settings = DownloadSettings(
            output_dir=job.output_dir,
            fmt=job.fmt,
            quality=job.quality,
            speed=job.speed,
            volume=getattr(job, "volume", 1.0),
            cookiefile=cfg.get("cookiefile", ""),
            cookies_browser=cfg.get("cookies_browser", "None"),
            use_deno=bool(cfg.get("use_deno")),
            embed_thumbnail=bool(cfg.get("embed_thumbnail")),
            crop_thumbnail=bool(cfg.get("crop_thumbnail")),
            embed_metadata=bool(cfg.get("embed_metadata")),
            track_num=bool(cfg.get("track_num")),
            skip_existing=bool(cfg.get("skip_existing")),
            suppress_js_warnings=bool(cfg.get("suppress_js_warnings", True)),
            max_retries=5,
            concurrent_downloads=max(1, int(cfg.get("concurrent_downloads") or 1)),
            concurrent_converts=max(1, int(cfg.get("concurrent_converts") or 1)),
            download_start_delay=max(0.0, float(cfg.get("download_start_delay") or 0.0)),
            runtime=self.download_runtime,
        )
        callbacks = DownloadCallbacks(
            log=self.log,
            is_cancelled=self.cancel_flag.is_set,
            on_metadata=self._on_job_metadata,
            on_item_queued=self._on_item_queued,
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

    def _on_all_finished(self):
        self.is_running = False
        self._set_system_sleep_state(prevent=False)
        cancelled = sum(1 for job in self.jobs if job.status == "cancelled")
        errors = sum(1 for job in self.jobs if job.status == "error")
        completed = sum(1 for job in self.jobs if job.status == "completed")
        total_done = sum(job.completed_videos for job in self.jobs)
        self.btn_start.setEnabled(bool(dependencies.get_ffmpeg_path()))
        self.btn_stop.setEnabled(False)
        self.lbl_current.setText("Idle")

        if cancelled:
            self.lbl_badge.setText("CANCELLED")
            self.lbl_badge.setObjectName("badgeRunning")
            self.log("SYSTEM", "Downloads cancelled.", "WARNING")
        elif errors:
            self.lbl_badge.setText(f"DONE ({errors} error{'s' if errors > 1 else ''})")
            self.lbl_badge.setObjectName("badgeRunning")
            self.log("SYSTEM", f"Finished: {completed} job(s) OK, {errors} with errors, {total_done} files total.", "WARNING")
        else:
            self.lbl_badge.setText("ALL DONE")
            self.lbl_badge.setObjectName("badgeReady")
            self.log("SYSTEM", f"All done. {completed} job(s), {total_done} files.", "SUCCESS")
            self.log("SYSTEM", f"Files saved to: {self.output_dir_edit.text()}", "SUCCESS")
            action = self.when_done_combo.currentText()
            if action != "Do nothing":
                threading.Thread(target=self._execute_power_action, args=(action,), daemon=True).start()

        self._refresh_badge_style()
        self._check_dependencies()
