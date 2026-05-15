import re
import threading, shutil
from dataclasses import dataclass, field

# ── Dependency Check ─────────────────────────────────────────────────────────

from yt_dlp.version import __version__ as YTDLP_VERSION

def get_ffmpeg_path():
    return shutil.which("ffmpeg")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    """Format seconds → H:MM:SS or M:SS."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def _parse_ffmpeg_progress(path: str) -> dict:
    """Kept for API compatibility; no longer used as primary progress source."""
    try:
        # Specify encoding explicitly to avoid relying on locale defaults
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return {}
    data: dict = {}
    for line in content.splitlines():
        line = line.strip()
        if "=" in line:
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip()
    return data

def _normalize_cookiesfrombrowser(spec: str):
    """Convert a browser cookie spec string into the tuple form yt-dlp expects."""
    spec = (spec or "").strip()
    if not spec or spec.lower() == "none":
        return None

    match = re.fullmatch(r"(?x)\s*(?P<name>[^+:]+)(?:\s*:\s*(?!:)(?P<profile>.+?))?(?:\s*::\s*(?P<container>.+))?\s*", spec)
    if not match:
        return (spec,)

    browser_name = match.group("name").strip()
    profile = match.group("profile")
    container = match.group("container")

    if profile is not None:
        profile = profile.strip() or None
    if container is not None:
        container = container.strip() or None

    values = [browser_name]
    if profile is not None or container is not None:
        values.append(profile)
    if container is not None:
        values.append(None)
        values.append(container)
    return tuple(values)

# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PlaylistJob:
    url: str
    output_dir: str
    fmt: str
    quality: str
    job_id: int
    speed: float          = 1.0
    playlist_title: str   = "Fetching..."
    total_videos: int     = 0
    completed_videos: int = 0
    failed_videos: int    = 0
    status: str           = "pending"
    error_msg: str        = ""
    start_time: float     = 0.0
    end_time: float       = 0.0
    output_folder: str    = ""
    # runtime-only fields (not constructor args)
    _ffmpeg_poll_stop:       threading.Event = field(default_factory=threading.Event,
                                                     init=False, repr=False)
    _current_video_duration: float           = field(default=0.0, init=False, repr=False)
    _last_prog_log:          float           = field(default=0.0, init=False, repr=False)
    # Progress monitoring: path of the output file ffmpeg is writing + start time
    _ffmpeg_output_path:     str             = field(default="",  init=False, repr=False)
    _ffmpeg_conv_start:      float           = field(default=0.0, init=False, repr=False)
    # Generation counter — prevents a stale poll thread from a previous video
    # in the same playlist job from outliving its intended lifetime.
    _ffmpeg_poll_gen:        int             = field(default=0,   init=False, repr=False)

# ── Colour & Theme ───────────────────────────────────────────────────────────

class Theme:
    BG     = "#0d1117"
    BG2    = "#161b22"
    BG3    = "#21262d"
    BG4    = "#30363d"
    ACCENT = "#58a6ff"
    GREEN  = "#3fb950"
    YELLOW = "#d29922"
    RED    = "#f85149"
    PURPLE = "#bc8cff"
    TEXT   = "#c9d1d9"
    MUTED  = "#6e7681"
    BORDER = "#30363d"
    WHITE  = "#f0f6fc"

LOG_COLOURS = {
    "INFO":     Theme.TEXT,
    "SUCCESS":  Theme.GREEN,
    "WARNING":  Theme.YELLOW,
    "ERROR":    Theme.RED,
    "DEBUG":    Theme.MUTED,
    "PROGRESS": Theme.ACCENT,
    "SYSTEM":   Theme.PURPLE,
}

FORMATS = {
    "m4a  — AAC  (Apple Music ★ recommended)": "m4a",
    "mp3  — MP3  (universal)":                 "mp3", 
    "flac — FLAC (lossless, large)":           "flac",
    "wav  — WAV  (uncompressed)":              "wav",
    "aiff — AIFF (Apple lossless)":            "aiff",
    "alac — ALAC (Apple Lossless Codec)":      "alac",
}

QUALITIES = {
    "Best (VBR)":           "0",
    "320 kbps":             "320",
    "256 kbps":             "256",
    "192 kbps":             "192",
    "128 kbps":             "128",
    "HE-AAC Mono 96kbps": "he_96",
    "HE-AAC Mono 64kbps": "he_64",
    "HE-AAC Mono 24kbps": "he_24",
}

# ── yt-dlp Logger Adapter ────────────────────────────────────────────────────

class YTLogger:
    """
    Routes yt-dlp log messages to our GUI log queue.

    cb_extract_dest(path: str):
        Called whenever yt-dlp logs "[ExtractAudio] Destination: <path>".
        This is wired unconditionally — regardless of whether the user has
        "Verbose Logs" enabled — because the progress monitor needs the
        destination path to poll the growing output file for size updates.
        Without this the monitor has no file to watch and stays silent.
    """

    def __init__(self, cb_info, cb_warn, cb_err, cb_debug=None,
                 cb_extract_dest=None):
        self._info         = cb_info
        self._warn         = cb_warn
        self._err          = cb_err
        self._debug        = cb_debug
        self._extract_dest = cb_extract_dest

    def _try_capture_dest(self, msg: str):
        """Extract the output path from a '[ExtractAudio] Destination:' line."""
        if self._extract_dest and "[ExtractAudio] Destination:" in msg:
            try:
                dest = msg.split("Destination:", 1)[1].strip()
                if dest:
                    self._extract_dest(dest)
            except Exception:
                pass

    def debug(self, msg):
        # Always attempt detination capture — before verbose gate.
        # yt-dlp routes its internal to_screen() calls through debug(),
        # so "[ExtractAudio] Destination:" arrives here.
        self._try_capture_dest(msg)

        if msg.startswith("[debug]"):
            if self._debug: self._debug(msg)
        else:
            if self._info:  self._info(msg)

    def info(self, msg):
        # Capture here too: some yt-dlp versions emit this via info() instead.
        self._try_capture_dest(msg)
        if self._info: self._info(msg)

    def warning(self, msg):
        if self._warn: self._warn(msg)

    def error(self, msg):
        if self._err: self._err(msg)
