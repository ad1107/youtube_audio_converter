#!/usr/bin/env python3

import queue
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk

from youtube_audio_converter import __version__
from youtube_audio_converter.dependencies import get_deno_path, get_ffmpeg_path
from .builder import GUIBuilderMixin
from .downloader import GUIDownloaderMixin
from .log_view import GUILogMixin
from .models import FORMATS, QUALITIES, PlaylistJob, Theme, YTDLP_VERSION
from .progress import GUIProgressMixin
from .settings import GUISettingsMixin


class YoutubeAudioConverter(
    tk.Tk,
    GUIBuilderMixin,
    GUISettingsMixin,
    GUIProgressMixin,
    GUILogMixin,
    GUIDownloaderMixin,
):
    def __init__(self):
        super().__init__()
        self.title(f"YouTube Audio/Video Downloader and Converter v{__version__}")
        self.minsize(1120, 700)
        self.configure(bg=Theme.BG)

        self.jobs: list[PlaylistJob] = []
        self.log_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.cancel_flag = threading.Event()
        self.playlist_row_widgets: list[tuple] = []
        self.active_progress_widgets: dict[str, dict] = {}

        self.var_output_dir = tk.StringVar(value=str(Path.home() / "Music" / "AudioBooks"))
        self.var_format = tk.StringVar(value=list(FORMATS.keys())[0])
        self.var_quality = tk.StringVar(value=list(QUALITIES.keys())[0])
        self.var_speed = tk.DoubleVar(value=1.0)
        self.var_volume = tk.DoubleVar(value=1.0)
        self.var_concurrent_downloads = tk.IntVar(value=2)
        self.var_concurrent_converts = tk.IntVar(value=1)
        self.var_download_start_delay = tk.DoubleVar(value=10.0)
        self.var_when_done = tk.StringVar(value="Do nothing")
        self.var_cookiefile = tk.StringVar(value="")
        self.var_cookies_browser = tk.StringVar(value="None")
        self.var_use_deno = tk.BooleanVar(value=False)
        self.var_autoscroll = tk.BooleanVar(value=True)
        self.var_suppress_js = tk.BooleanVar(value=True)
        self.var_run_view = tk.StringVar(value="progress")
        self.var_thumbnail = tk.BooleanVar(value=True)
        self.var_crop_thumb = tk.BooleanVar(value=True)
        self.var_metadata = tk.BooleanVar(value=True)
        self.var_track_num = tk.BooleanVar(value=True)
        self.var_skip_existing = tk.BooleanVar(value=True)

        self._apply_ttk_style()
        self._build_ui()
        self._after_build()

    def _after_build(self):
        self._check_dependencies()
        self._poll_log_queue()
        self.log("SYSTEM", "YouTube Audio/Video Downloader and Converter", "SYSTEM")
        self.log("SYSTEM", "Supported audio: M4A, HE-AAC, MP3, Opus, FLAC, WAV, AIFF, ALAC", "INFO")
        self.log("SYSTEM", "Supported video: MP4, MKV, WebM", "INFO")
        self.log("SYSTEM", "Tip: Add playlist or single-video URLs; type is auto-detected", "INFO")
        missing = [] if get_ffmpeg_path() else ["ffmpeg"]
        if missing:
            self.log("SYSTEM", f"Missing: {', '.join(missing)}", "WARNING")
            if "ffmpeg" in missing:
                self.log("SYSTEM", "https://ffmpeg.org", "WARNING")

    def _check_dependencies(self):
        has_ffmpeg = bool(get_ffmpeg_path())
        has_deno = bool(get_deno_path())

        missing = []
        if not has_ffmpeg:
            missing.append("ffmpeg")

        status_text = f"yt-dlp {YTDLP_VERSION}"
        if has_ffmpeg:
            status_text += "  ffmpeg"
        if has_deno:
            status_text += "  deno"

        if not missing:
            self.lbl_dep_status.config(text=status_text, fg=Theme.GREEN)
        else:
            self.lbl_dep_status.config(text=f"Missing: {', '.join(missing)}", fg=Theme.YELLOW)
            if "ffmpeg" in missing:
                self.btn_start.config(state="disabled")

    def log(self, source: str, message: str, level: str = "INFO"):
        self.log_queue.put((source, message, level, datetime.now()))
