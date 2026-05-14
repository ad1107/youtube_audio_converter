#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════╗
║       AudioBook → Apple Music Converter               ║
║  YouTube Playlists → M4A/MP3 with metadata & art     ║
╚═══════════════════════════════════════════════════════╝

Usage:
    python -m music_audiobook_importer --gui
"""

import threading
import queue
from datetime import datetime
from pathlib import Path
import tkinter as tk

# Single source of truth for shared state, constants and dependency checks
from models_utils import (
    YTDLP_VERSION,
    FORMATS, QUALITIES, Theme,
    PlaylistJob,
    get_ffmpeg_path,
)
from gui_builder import GUIBuilderMixin
from gui_downloader import GUIDownloaderMixin


class YoutubeAudioConverter(tk.Tk, GUIBuilderMixin, GUIDownloaderMixin):

    def __init__(self):
        super().__init__()
        self.title("YouTube Audio Downloader and Converter v1.0.0")
        self.geometry("1200x820")
        self.minsize(960, 660)
        self.configure(bg=Theme.BG)

        self.jobs: list[PlaylistJob]           = []
        self.log_queue: queue.Queue            = queue.Queue()
        self.is_running                        = False
        self.cancel_flag                       = threading.Event()
        self.playlist_row_widgets: list[tuple] = []

        self.var_output_dir    = tk.StringVar(value=str(Path.home() / "Music" / "AudioBooks"))
        self.var_format        = tk.StringVar(value=list(FORMATS.keys())[0])
        self.var_quality       = tk.StringVar(value=list(QUALITIES.keys())[0])
        self.var_speed         = tk.DoubleVar(value=1.0)
        self.var_concurrent    = tk.IntVar(value=2)
        self.var_when_done     = tk.StringVar(value="Do nothing")
        # Bug 3 FIX: the old playlist/single-video checkbox has been removed.
        # URL type is auto-detected at download time (see gui_downloader.py).
        self.var_thumbnail     = tk.BooleanVar(value=True)
        self.var_crop_thumb    = tk.BooleanVar(value=True)
        self.var_metadata      = tk.BooleanVar(value=True)
        self.var_track_num     = tk.BooleanVar(value=True)
        self.var_skip_existing = tk.BooleanVar(value=True)

        self._apply_ttk_style()
        self._build_ui()
        self._after_build()

    def _after_build(self):
        self._check_dependencies()
        self._poll_log_queue()
        self.log("SYSTEM", "AudioBook → Apple Music Converter", "SYSTEM")
        self.log("SYSTEM", "Supported output: M4A · MP3 · FLAC · WAV · AIFF · ALAC", "INFO")
        self.log("SYSTEM", "Tip: Add playlist or single-video URLs — type auto-detected", "INFO")
        self.log("SYSTEM", "Tip: Use 64/96 kbps for audiobooks — saves space, sounds fine", "INFO")
        missing = [] if get_ffmpeg_path() else ["ffmpeg (system)"]
        if missing:
            self.log("SYSTEM", f"⚠ Missing: {', '.join(missing)}", "WARNING")
            if "ffmpeg"  in " ".join(missing): self.log("SYSTEM", "  https://ffmpeg.org",  "WARNING")

    def _check_dependencies(self):
        missing = [] if get_ffmpeg_path() else ["ffmpeg (system)"]
        if not missing:
            self.lbl_dep_status.config(
                text=f"✓ yt-dlp {YTDLP_VERSION}  ✓ ffmpeg", fg=Theme.GREEN)
        else:
            self.lbl_dep_status.config(text=f"⚠ Missing: {', '.join(missing)}", fg=Theme.YELLOW)
            if "ffmpeg" in " ".join(missing):
                self.btn_start.config(state="disabled")

    def log(self, source: str, message: str, level: str = "INFO"):
        self.log_queue.put((source, message, level, datetime.now()))