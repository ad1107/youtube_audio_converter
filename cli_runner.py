import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp

from ffmpeg_dl import get_ffmpeg_path, get_deno_path
from models_utils import FORMATS, QUALITIES, _fmt_duration, _normalize_cookiesfrombrowser


def _detect_no_playlist(url: str) -> bool:
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


def _parse_source_line(line: str):
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if "|" in text:
        left, right = text.split("|", 1)
        label = left.strip()
        url = right.strip()
        if url:
            return label or None, url
        return None
    return None, text


def _load_sources(urls, input_files):
    items = []
    for value in urls or []:
        text = value.strip()
        if text:
            items.append((None, text))
    for file_path in input_files or []:
        path = Path(file_path)
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_source_line(line)
            if parsed:
                items.append(parsed)
    return items


@dataclass
class CliJob:
    label: str | None
    url: str


class ConsoleLogger:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def debug(self, msg):
        if self.verbose or "ffmpeg command line:" in msg:
            print(msg)

    def info(self, msg):
        print(msg)

    def warning(self, msg):
        if any(x in msg.lower() for x in ["javascript runtime", "[jsc]", "n challenge", "deno process"]):
            return
        print(msg, file=sys.stderr)

    def error(self, msg):
        print(msg, file=sys.stderr)


def build_parser():
    parser = argparse.ArgumentParser(description="YouTube audiobook downloader and converter")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--gui", action="store_true", help="Force GUI mode")
    parser.add_argument("--url", action="append", default=[], help="YouTube URL to download (repeatable)")
    parser.add_argument("--input", action="append", default=[], help="Text file with one URL per line")
    parser.add_argument("--output", default=str(Path.home() / "Music" / "AudioBooks"), help="Output folder")
    parser.add_argument("--format", choices={v for v in FORMATS.values()}, default="m4a", help="Output format")
    parser.add_argument("--quality", default="0", help="Audio quality or HE-AAC preset value")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed, e.g. 1.3")
    parser.add_argument("--concurrent", type=int, default=2, help="Concurrent jobs")
    parser.add_argument("--cookiefile", default="", help="Path to cookies.txt")
    parser.add_argument("--cookies-from-browser", dest="cookies_from_browser", default="", help="Browser name or browser:profile")
    parser.add_argument("--no-thumbnail", action="store_true", help="Do not embed thumbnails")
    parser.add_argument("--no-crop-thumbnail", action="store_true", help="Do not crop thumbnails to square")
    parser.add_argument("--no-metadata", action="store_true", help="Do not embed metadata")
    parser.add_argument("--no-track-num", action="store_true", help="Do not add track numbers")
    parser.add_argument("--no-skip-existing", action="store_true", help="Overwrite existing files")
    parser.add_argument("--use-deno", action="store_true", help="Use Deno JS engine for remote components (mitigates YouTube blocks)")
    parser.add_argument("--download-dependencies", nargs="+", choices=["ffmpeg", "deno", "all"], help="Automatically download missing dependencies")
    parser.add_argument("--verbose", action="store_true", help="Show verbose yt-dlp debug output")
    return parser


def _build_postprocessors(fmt: str, quality: str, speed: float, embed_thumbnail: bool, crop_thumb: bool, embed_metadata: bool, track_num: bool):
    is_he_aac = quality.startswith("he_")
    is_lossless = fmt in ["flac", "wav", "aiff", "alac"]

    pp_extract = {"key": "FFmpegExtractAudio", "preferredcodec": fmt}
    if not is_he_aac and not is_lossless:
        pp_extract["preferredquality"] = quality

    postprocessors = [pp_extract]
    if embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
    if embed_thumbnail:
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
        postprocessors.append({"key": "EmbedThumbnail"})

    pp_args: dict = {}
    af = None
    if speed != 1.0:
        if speed < 0.5:
            af = f"atempo=0.5,atempo={speed / 0.5:.4f}"
        else:
            af = f"atempo={speed}"

    if is_he_aac:
        bitrate = quality.split("_")[1] + "k"
        extract_args = ["-c:a", "libfdk_aac", "-profile:a", "aac_he", "-b:a", bitrate, "-ac", "1", "-ar", "44100"]
        if af:
            extract_args.extend(["-af", af])
        pp_args["extractaudio+ffmpeg_o"] = extract_args
    elif af:
        encoder_map = {
            "m4a": "aac",
            "mp3": "libmp3lame",
            "flac": "flac",
            "wav": "pcm_s16le",
            "aiff": "pcm_s16be",
            "alac": "alac",
        }
        enc = encoder_map.get(fmt, "aac")
        pp_args["extractaudio+ffmpeg_o"] = ["-c:a", enc, "-af", af]

    if embed_thumbnail and crop_thumb:
        crop_vf = "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"
        pp_args["thumbnailsconvertor+ffmpeg_o"] = ["-c:v", "mjpeg", "-vf", crop_vf]

    return postprocessors, pp_args


def _run_one(job: CliJob, args, logger: ConsoleLogger) -> bool:
    no_playlist = _detect_no_playlist(job.url)
    fmt = args.format
    quality = args.quality
    out_dir = Path(args.output)
    if job.label:
        out_dir = out_dir / job.label
    out_dir.mkdir(parents=True, exist_ok=True)

    postprocessors, pp_args = _build_postprocessors(
        fmt=fmt,
        quality=quality,
        speed=args.speed,
        embed_thumbnail=not args.no_thumbnail,
        crop_thumb=not args.no_crop_thumbnail,
        embed_metadata=not args.no_metadata,
        track_num=not args.no_track_num,
    )

    filename_tmpl = "%(playlist_index)02d - %(title)s.%(ext)s" if not args.no_track_num else "%(title)s.%(ext)s"
    if job.label:
        outtmpl = os.path.join(str(out_dir), filename_tmpl)
    else:
        outtmpl = os.path.join(str(out_dir), "%(playlist_title,playlist)s", filename_tmpl)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": postprocessors,
        "postprocessor_args": pp_args,
        "writethumbnail": not args.no_thumbnail,
        "noplaylist": no_playlist,
        "ignoreerrors": True,
        "no_warnings": False,
        "quiet": True,
        "color": "no_color",
        "nooverwrites": not args.no_skip_existing,
        "logger": logger,
    }

    if args.use_deno:
        deno_path = get_deno_path()
        if deno_path:
            ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}}
            ydl_opts["remote_components"] = ["ejs:github"]
            print(f"[INFO] Using Deno JS engine for remote components")
        else:
            print("[WARNING] --use-deno specified but Deno is not found in bin/ or PATH. Ignoring.", file=sys.stderr)
            print("[INFO] Run 'python main.py --download-dependencies deno' to install it automatically.", file=sys.stderr)

    if args.cookiefile:
        if not os.path.isfile(args.cookiefile):
            print(f"[ERROR] Cookies file not found: {args.cookiefile}", file=sys.stderr)
            return False
        ydl_opts["cookiefile"] = args.cookiefile
    elif args.cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = _normalize_cookiesfrombrowser(args.cookies_from_browser)

    def progress_hook(d):
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct = (downloaded / total * 100) if total else 0
            speed = d.get("speed") or 0
            eta = d.get("eta")
            fname = os.path.basename(d.get("filename", ""))
            speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "…"
            eta_str = f"ETA {eta}s" if eta is not None else ""
            print(f"[{job.url[:36]}] {fname[:40]}  {pct:5.1f}%  {speed_str}  {eta_str}")
        elif status == "finished":
            fname = os.path.basename(d.get("filename", ""))
            print(f"[{job.url[:36]}] Download complete: {fname}")

    ydl_opts["progress_hooks"] = [progress_hook]
    ydl_opts["concurrent_fragment_downloads"] = 4

    print(f"[INFO] Fetching: {job.url}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(job.url, download=False)
            if info is None:
                print(f"[ERROR] Could not retrieve info: {job.url}")
                return False
            title = info.get("title") or ("Unknown Playlist" if "entries" in info else "Single Video")
            total = len([e for e in (info.get("entries") or []) if e]) if "entries" in info else 1
            print(f"[INFO] {title} ({total} item(s)) → {fmt.upper()} @ {quality}")
            ydl.download([job.url])
        return True
    except Exception as e:
        print(f"[ERROR] {job.url}: {e}", file=sys.stderr)
        return False


def run_cli(args) -> int:
    if getattr(args, "download_dependencies", None):
        from ffmpeg_dl import download_ffmpeg_if_needed, download_deno_if_needed
        deps = args.download_dependencies
        if "ffmpeg" in deps or "all" in deps:
            print("[INFO] Checking/Downloading FFmpeg...")
            download_ffmpeg_if_needed()
        if "deno" in deps or "all" in deps:
            print("[INFO] Checking/Downloading Deno...")
            download_deno_if_needed()
        print("[INFO] Dependency installation finished.")
        return 0

    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        print("[ERROR] ffmpeg was not found in PATH or the local bin folder.", file=sys.stderr)
        print("[INFO] Run 'python main.py --download-dependencies ffmpeg' to install it automatically.", file=sys.stderr)
        return 1

    sources = _load_sources(args.url, args.input)
    if not sources:
        print("[ERROR] No URLs provided. Use --url and/or --input.", file=sys.stderr)
        return 1

    jobs = [CliJob(label=label, url=url) for label, url in sources]
    logger = ConsoleLogger(verbose=args.verbose)

    print(f"[INFO] Launching {len(jobs)} job(s) — {args.concurrent} concurrent")
    ok_count = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrent)) as ex:
        future_map = {ex.submit(_run_one, job, args, logger): job for job in jobs}
        for fut in as_completed(future_map):
            if fut.result():
                ok_count += 1

    print(f"[INFO] Finished — {ok_count} job(s) OK, {len(jobs) - ok_count} with errors")
    return 0 if ok_count == len(jobs) else 1