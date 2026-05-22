from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yt_dlp

from ..dependencies import get_deno_path
from .download_types import DownloadCallbacks, DownloadItem, DownloadSettings, FailedItem
from .ffmpeg_progress import ffmpeg_progress_context
from .formats import (
    format_quality_summary,
    get_format_spec,
    normalize_quality,
    supports_audio_filters,
)
from .formatting import fmt_duration
from .media import (
    build_postprocessors,
    clone_postprocessors,
    existing_output_path,
    filename_info,
    item_template,
    item_url,
    output_folder_for,
)
from .runtime import DownloadRuntime
from .urls import detect_no_playlist, url_kind_label
from .ydl_options import build_ydl_options, build_yt_logger


def run_download_job(job, settings: DownloadSettings, callbacks: DownloadCallbacks) -> list[FailedItem]:
    failures: list[FailedItem] = []
    job.status = "running"
    job.start_time = time.time()
    job.completed_videos = 0
    job.failed_videos = 0
    job.error_msg = ""

    try:
        settings.quality = normalize_quality(settings.fmt, settings.quality)
    except ValueError as exc:
        failure = _record_failure(job, failures, callbacks, None, str(exc), job.url)
        job.status = "error"
        job.error_msg = failure.reason
        job.total_videos = max(getattr(job, "total_videos", 0), 1)
        job.failed_videos = 1
        job.end_time = time.time()
        return failures

    if settings.runtime is None:
        settings.runtime = DownloadRuntime(
            settings.concurrent_downloads,
            settings.concurrent_converts,
            settings.download_start_delay,
        )

    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    if settings.use_deno and not get_deno_path():
        callbacks.log(job.url[:60], "Use Deno is enabled, but Deno was not found; continuing without it.", "WARNING")
    if not supports_audio_filters(settings.fmt) and (settings.speed != 1.0 or settings.volume != 1.0):
        callbacks.log(
            job.url[:60],
            "Playback speed and volume filters are audio-only; ignoring them for video output.",
            "WARNING",
        )

    no_playlist = detect_no_playlist(job.url)
    kind_label = url_kind_label(job.url)
    callbacks.log(job.url[:60], f"Auto-detected as {kind_label}; fetching metadata...", "INFO")

    try:
        metadata_opts = build_ydl_options(
            settings,
            outtmpl=None,
            logger=build_yt_logger(job, settings, callbacks),
            noplaylist=no_playlist,
            include_postprocessors=False,
            ignoreerrors=True,
        )
        with yt_dlp.YoutubeDL(metadata_opts) as ydl:
            info = ydl.extract_info(job.url, download=False)
    except Exception as exc:
        failure = _record_failure(job, failures, callbacks, None, str(exc), job.url)
        job.status = "error"
        job.error_msg = failure.reason
        job.total_videos = max(getattr(job, "total_videos", 0), 1)
        job.failed_videos = 1
        job.end_time = time.time()
        return failures

    if info is None:
        failure = _record_failure(job, failures, callbacks, None, "Could not retrieve metadata", job.url)
        job.status = "error"
        job.error_msg = failure.reason
        job.total_videos = max(getattr(job, "total_videos", 0), 1)
        job.failed_videos = 1
        job.end_time = time.time()
        return failures

    is_playlist = "entries" in info and not no_playlist
    entries = [entry for entry in (info.get("entries") or []) if entry] if is_playlist else [info]
    title = info.get("title") or ("Unknown Playlist" if is_playlist else "Single Video")
    job.playlist_title = title
    job.total_videos = len(entries)
    job.output_folder = output_folder_for(settings.output_dir, getattr(job, "label", None), title, job.job_id)
    Path(job.output_folder).mkdir(parents=True, exist_ok=True)

    spec = get_format_spec(settings.fmt)
    speed_note = f"  speed {settings.speed}x" if spec.supports_audio_filters and settings.speed != 1.0 else ""
    volume_note = f"  volume {settings.volume}x" if spec.supports_audio_filters and settings.volume != 1.0 else ""
    callbacks.log(
        job.playlist_title,
        f"Found {job.total_videos} item(s) -> {format_quality_summary(settings.fmt, settings.quality)}{speed_note}{volume_note}",
        "INFO",
    )
    callbacks.on_metadata(job, job.playlist_title, job.total_videos, job.output_folder)

    if callbacks.is_cancelled():
        job.status = "cancelled"
        return failures

    callbacks.log(
        job.playlist_title,
        f"Starting download -> {job.output_folder} "
        f"(DL {settings.concurrent_downloads}, convert {settings.concurrent_converts}, "
        f"start gap {settings.download_start_delay:g}s)",
        "INFO",
    )

    pending_items: list[DownloadItem] = []
    for index, entry in enumerate(entries, start=1):
        if callbacks.is_cancelled():
            job.status = "cancelled"
            break

        item = _make_item(entry, job, settings, index, is_playlist)
        callbacks.on_item_queued(job, item, index)

        if settings.skip_existing:
            existing = existing_output_path(item.outtmpl, item.info, settings.fmt)
            if existing:
                job.completed_videos += 1
                callbacks.log(job.playlist_title, f"Skipped existing: {item.title}", "INFO")
                callbacks.on_item_skipped(job, item, existing)
                continue

        pending_items.append(item)

    if pending_items and job.status != "cancelled":
        workers = _item_worker_count(len(pending_items), settings)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(_download_item, job, item, settings, callbacks): item
                for item in pending_items
            }
            for future in as_completed(future_map):
                item = future_map[future]
                if callbacks.is_cancelled():
                    job.status = "cancelled"
                try:
                    success = future.result()
                except Exception as exc:
                    success = False
                    callbacks.log(job.playlist_title, f"{item.title}: {exc}", "ERROR")

                if callbacks.is_cancelled():
                    job.status = "cancelled"
                    continue

                if success:
                    job.completed_videos += 1
                    callbacks.on_item_done(job, item, item.expected_path)
                else:
                    job.failed_videos += 1
                    _record_failure(job, failures, callbacks, item, "Download or conversion failed", item.url)

    if job.status != "cancelled":
        job.status = "error" if job.failed_videos else "completed"
    job.end_time = time.time()
    return failures


def _item_worker_count(item_count: int, settings: DownloadSettings) -> int:
    buffer_workers = max(8, settings.concurrent_downloads * 2)
    wanted = settings.concurrent_downloads + settings.concurrent_converts + buffer_workers
    return max(1, min(item_count, wanted))


def _download_item(job, item: DownloadItem, settings: DownloadSettings, callbacks: DownloadCallbacks) -> bool:
    last_error = ""
    attempts = max(1, int(settings.max_retries or 1))

    for attempt in range(1, attempts + 1):
        if callbacks.is_cancelled():
            return False
        if attempt > 1:
            callbacks.log(job.playlist_title, f"Retrying {item.title} (attempt {attempt}/{attempts})", "WARNING")
            time.sleep(2)

        postprocessors, postprocessor_args = clone_postprocessors(
            *build_postprocessors(
                fmt=settings.fmt,
                quality=settings.quality,
                speed=settings.speed,
                volume=settings.volume,
                embed_thumbnail=settings.embed_thumbnail,
                crop_thumb=settings.crop_thumbnail,
                embed_metadata=settings.embed_metadata,
                skip_existing=settings.skip_existing,
            )
        )

        download_slot_acquired = False
        download_slot_released = False

        def release_download_slot():
            nonlocal download_slot_released
            if download_slot_acquired and not download_slot_released:
                settings.runtime.download_gate.release()
                download_slot_released = True

        def progress_hook(data, j=job, it=item):
            _download_progress(callbacks, j, it, data)

        def postprocessor_hook(data, j=job, it=item):
            if data.get("status") == "started":
                release_download_slot()
            callbacks.on_postprocessor(j, it, data)

        ydl_opts = build_ydl_options(
            settings,
            outtmpl=item.outtmpl,
            logger=build_yt_logger(job, settings, callbacks),
            noplaylist=True,
            include_postprocessors=True,
            ignoreerrors=False,
            postprocessors=postprocessors,
            postprocessor_args=postprocessor_args,
            progress_hook=progress_hook,
            postprocessor_hook=postprocessor_hook,
        )

        try:
            if not settings.runtime.download_gate.acquire(callbacks.is_cancelled):
                return False
            download_slot_acquired = True
            callbacks.on_item_started(job, item, item.index)

            with ffmpeg_progress_context(
                lambda progress, j=job, it=item: callbacks.on_ffmpeg_progress(j, it, progress),
                conversion_gate=settings.runtime.conversion_gate,
            ):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.download([item.url])
            if result == 0 and _item_output_exists(item):
                return True
            if result == 0 and not item.expected_path:
                return True
            last_error = f"yt-dlp returned {result}, output not found"
        except yt_dlp.utils.DownloadError as exc:
            last_error = str(exc)
            if callbacks.is_cancelled():
                return False
        except Exception as exc:
            last_error = str(exc)
        finally:
            release_download_slot()

        if last_error:
            callbacks.log(job.playlist_title, f"{item.title}: {last_error}", "ERROR")

    return False


def _download_progress(callbacks: DownloadCallbacks, job, item: DownloadItem, data: dict) -> None:
    if callbacks.is_cancelled():
        raise yt_dlp.utils.DownloadError("Cancelled by user")
    callbacks.on_download_progress(job, item, data)


def _item_output_exists(item: DownloadItem) -> bool:
    return bool(item.expected_path and os.path.isfile(item.expected_path) and os.path.getsize(item.expected_path) > 0)


def _make_item(entry: dict, job, settings: DownloadSettings, index: int, is_playlist: bool) -> DownloadItem:
    title = entry.get("title") or f"Track {index:02d}"
    info = filename_info(entry, job.playlist_title, index, settings.fmt)
    outtmpl = item_template(job.output_folder, index, settings.track_num, is_playlist, title=title)
    expected_path = existing_output_path(outtmpl, info, settings.fmt) or _expected_path(outtmpl, info, settings.fmt)
    return DownloadItem(
        index=index,
        title=title,
        url=item_url(entry, job.url),
        outtmpl=outtmpl,
        expected_path=expected_path,
        duration=float(entry.get("duration") or 0),
        info=info,
    )


def _expected_path(outtmpl: str, info: dict, fmt: str) -> str:
    from .media import expected_output_path

    return expected_output_path(outtmpl, info, fmt)


def _record_failure(
    job,
    failures: list[FailedItem],
    callbacks: DownloadCallbacks,
    item: DownloadItem | None,
    reason: str,
    fallback_url: str,
) -> FailedItem:
    failure = FailedItem(
        title=item.title if item else getattr(job, "playlist_title", "") or fallback_url,
        url=item.url if item else fallback_url,
        source_url=job.url,
        playlist_title=getattr(job, "playlist_title", "") or "Unknown",
        reason=reason,
        index=item.index if item else 0,
    )
    failures.append(failure)
    callbacks.on_item_failed(job, item, failure)
    callbacks.log(failure.playlist_title, f"Failed: {failure.title} ({reason})", "ERROR")
    return failure


def summarize_elapsed(job) -> str:
    if not getattr(job, "end_time", 0):
        return "0:00"
    return fmt_duration(job.end_time - job.start_time)
