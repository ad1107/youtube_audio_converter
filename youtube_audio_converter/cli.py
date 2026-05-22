import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .core.download import DownloadCallbacks, DownloadSettings, run_download_job
from .core.formats import FORMAT_SPECS, format_codes, normalize_quality, quality_options_for_format
from .core.formatting import fmt_duration, fmt_speed
from .core.runtime import DownloadRuntime
from .core.urls import load_sources
from .dependencies import get_deno_path, get_ffmpeg_path
from .gui.models import PlaylistJob


class ConsoleReporter:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._lock = threading.Lock()

    def log(self, source: str, message: str, level: str = "INFO"):
        stream = sys.stderr if level in {"ERROR", "WARNING"} else sys.stdout
        encoding = getattr(stream, "encoding", None) or "utf-8"
        message = str(message).encode(encoding, errors="replace").decode(encoding, errors="replace")
        source = str(source or "").encode(encoding, errors="replace").decode(encoding, errors="replace")
        with self._lock:
            if source and source.upper() != "SYSTEM":
                print(f"[{level:<8s}] [{source[:38]:<38s}] {message}", file=stream, flush=True)
            else:
                print(f"[{level:<8s}] {message}", file=stream, flush=True)


def build_parser():
    parser = argparse.ArgumentParser(description="YouTube audio/video downloader and converter", allow_abbrev=False)
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--gui", action="store_true", help="Force GUI mode")
    parser.add_argument("--list-formats", action="store_true", help="Show supported formats and format-specific quality values")
    parser.add_argument("--url", action="append", default=[], help="YouTube URL to download (repeatable)")
    parser.add_argument("--input", action="append", default=[], help="Text file with one URL per line")
    parser.add_argument("--output", default=str(Path.home() / "Music" / "AudioBooks"), help="Output folder")
    parser.add_argument("--format", choices=format_codes(), default="m4a", help="Output format")
    parser.add_argument("--quality", default=None, help="Format-specific quality value; omit for that format's default")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed, e.g. 1.3")
    parser.add_argument("--concurrent-downloads", type=int, default=2, help="Concurrent track downloads")
    parser.add_argument("--concurrent-converts", type=int, default=1, help="Concurrent FFmpeg conversions")
    parser.add_argument("--download-start-delay", type=float, default=10.0, help="Seconds to wait before starting the next download")
    parser.add_argument("--volume", type=float, default=1.0, help="FFmpeg volume multiplier, e.g. 0.5 or 2.0")
    parser.add_argument("--cookiefile", default="", help="Path to cookies.txt")
    parser.add_argument("--cookies-from-browser", dest="cookies_from_browser", default="", help="Browser name or browser:profile")
    parser.add_argument("--no-thumbnail", action="store_true", help="Do not embed thumbnails")
    parser.add_argument("--no-crop-thumbnail", action="store_true", help="Do not crop thumbnails to square")
    parser.add_argument("--no-metadata", action="store_true", help="Do not embed metadata")
    parser.add_argument("--no-track-num", action="store_true", help="Do not add track numbers")
    parser.add_argument("--no-skip-existing", action="store_true", help="Overwrite existing files")
    parser.add_argument("--use-deno", action="store_true", help="Use Deno JS engine for remote components")
    parser.add_argument("--download-dependencies", nargs="+", choices=["ffmpeg", "deno", "all"], help="Automatically download missing dependencies")
    parser.add_argument("--verbose", action="store_true", help="Show verbose yt-dlp debug output")
    return parser


def run_cli(args) -> int:
    if getattr(args, "list_formats", False):
        _print_format_table()
        return 0

    if getattr(args, "download_dependencies", None):
        from .dependencies import download_deno_if_needed, download_ffmpeg_if_needed

        deps = args.download_dependencies
        if "ffmpeg" in deps or "all" in deps:
            print("[INFO] Checking/Downloading FFmpeg...")
            download_ffmpeg_if_needed()
        if "deno" in deps or "all" in deps:
            print("[INFO] Checking/Downloading Deno...")
            download_deno_if_needed()
        print("[INFO] Dependency installation finished.")
        return 0

    if not get_ffmpeg_path():
        print("[ERROR] ffmpeg was not found in PATH or the local bin folder.", file=sys.stderr)
        print("[INFO] Run 'python main.py --download-dependencies ffmpeg' to install it automatically.", file=sys.stderr)
        return 1

    sources = load_sources(args.url, args.input)
    if not sources:
        print("[ERROR] No URLs provided. Use --url and/or --input.", file=sys.stderr)
        return 1

    if args.use_deno and not get_deno_path():
        print("[WARNING] --use-deno was set, but Deno was not found in bin/ or PATH.", file=sys.stderr)
    if args.volume <= 0:
        print("[ERROR] --volume must be greater than 0.", file=sys.stderr)
        return 1
    if args.speed <= 0:
        print("[ERROR] --speed must be greater than 0.", file=sys.stderr)
        return 1
    if args.concurrent_downloads <= 0:
        print("[ERROR] --concurrent-downloads must be greater than 0.", file=sys.stderr)
        return 1
    if args.concurrent_converts <= 0:
        print("[ERROR] --concurrent-converts must be greater than 0.", file=sys.stderr)
        return 1
    if args.download_start_delay < 0:
        print("[ERROR] --download-start-delay must be 0 or greater.", file=sys.stderr)
        return 1
    try:
        args.quality = normalize_quality(args.format, args.quality)
    except ValueError as exc:
        valid = ", ".join(option.value for option in quality_options_for_format(args.format))
        print(f"[ERROR] {exc}", file=sys.stderr)
        print(f"[INFO] Valid --quality values for --format {args.format}: {valid}", file=sys.stderr)
        return 1

    jobs = []
    for index, (label, url) in enumerate(sources):
        job = PlaylistJob(
            url=url,
            output_dir=args.output,
            fmt=args.format,
            quality=args.quality,
            speed=args.speed,
            volume=args.volume,
            job_id=index,
            label=label,
        )
        jobs.append(job)

    download_slots = max(1, args.concurrent_downloads)
    convert_slots = max(1, args.concurrent_converts)
    start_delay = max(0.0, args.download_start_delay)
    runtime = DownloadRuntime(download_slots, convert_slots, start_delay)

    reporter = ConsoleReporter(verbose=args.verbose)
    reporter.log(
        "SYSTEM",
        f"Launching {len(jobs)} source(s), DL {download_slots}, convert {convert_slots}, start gap {start_delay:g}s",
        "INFO",
    )

    ok_count = 0
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as executor:
        future_map = {executor.submit(_run_cli_job, job, args, reporter, runtime, download_slots, convert_slots, start_delay): job for job in jobs}
        for future in as_completed(future_map):
            job = future_map[future]
            try:
                future.result()
            except Exception as exc:
                job.status = "error"
                reporter.log(job.playlist_title, f"Unhandled error: {exc}", "ERROR")
            if job.status == "completed":
                ok_count += 1

    reporter.log("SYSTEM", f"Finished: {ok_count} job(s) OK, {len(jobs) - ok_count} with errors", "INFO")
    return 0 if ok_count == len(jobs) else 1


def _run_cli_job(
    job: PlaylistJob,
    args,
    reporter: ConsoleReporter,
    runtime: DownloadRuntime,
    download_slots: int,
    convert_slots: int,
    start_delay: float,
):
    settings = DownloadSettings(
        output_dir=job.output_dir,
        fmt=job.fmt,
        quality=job.quality,
        speed=job.speed,
        volume=args.volume,
        cookiefile=args.cookiefile,
        cookies_browser=args.cookies_from_browser,
        use_deno=args.use_deno,
        embed_thumbnail=not args.no_thumbnail,
        crop_thumbnail=not args.no_crop_thumbnail,
        embed_metadata=not args.no_metadata,
        track_num=not args.no_track_num,
        skip_existing=not args.no_skip_existing,
        suppress_js_warnings=True,
        verbose=args.verbose,
        max_retries=5,
        concurrent_downloads=download_slots,
        concurrent_converts=convert_slots,
        download_start_delay=start_delay,
        runtime=runtime,
    )

    def on_download_progress(active_job, item, data):
        status = data.get("status")
        if status == "downloading":
            now = time.time()
            if now - getattr(active_job, "_last_prog_log", 0.0) < 2.0:
                return
            active_job._last_prog_log = now
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes") or 0
            pct = downloaded / total * 100 if total else 0
            eta = data.get("eta")
            eta_text = f" ETA {eta}s" if eta is not None else ""
            reporter.log(
                active_job.playlist_title,
                f"Download {item.title[:36]} {pct:5.1f}% {fmt_speed(data.get('speed'))}{eta_text}",
                "PROGRESS",
            )
        elif status == "finished":
            if getattr(item, "_download_finished_logged", False):
                return
            item._download_finished_logged = True
            reporter.log(active_job.playlist_title, f"Download complete: {item.title}", "SUCCESS")

    def on_ffmpeg_progress(active_job, item, progress):
        if getattr(progress, "completed", False):
            if getattr(item, "_ffmpeg_complete_logged", False):
                return
            item._ffmpeg_complete_logged = True
            reporter.log(active_job.playlist_title, f"FFmpeg complete; finalizing: {item.title}", "PROGRESS")
            return

        now = time.time()
        if now - getattr(active_job, "_last_ffmpeg_prog_log", 0.0) < 2.0:
            return
        active_job._last_ffmpeg_prog_log = now
        expected = item.duration / active_job.speed if item.duration and active_job.speed > 0 else 0
        pct_text = f" {min(progress.time_seconds / expected * 100, 99):.0f}%" if expected else ""
        speed_text = f" {progress.speed}" if progress.speed else ""
        reporter.log(
            active_job.playlist_title,
            f"FFmpeg {fmt_duration(progress.time_seconds)}{pct_text}{speed_text}",
            "PROGRESS",
        )

    callbacks = DownloadCallbacks(
        log=reporter.log,
        on_item_done=lambda active_job, item, path: reporter.log(active_job.playlist_title, f"Saved: {item.title}", "SUCCESS"),
        on_download_progress=on_download_progress,
        on_ffmpeg_progress=on_ffmpeg_progress,
    )

    run_download_job(job, settings, callbacks)
    level = "WARNING" if job.failed_videos else "SUCCESS"
    reporter.log(
        job.playlist_title,
        f"Done {job.completed_videos}/{job.total_videos} files ({job.failed_videos} failed)",
        level,
    )


def _print_format_table() -> None:
    print("Supported formats and qualities:")
    for spec in FORMAT_SPECS.values():
        qualities = ", ".join(option.value for option in spec.quality_options)
        kind = "video" if spec.media_kind == "video" else "audio"
        print(f"  {spec.code:<7s} {kind:<5s} .{spec.final_ext:<4s} {spec.label}")
        print(f"          qualities: {qualities}")
