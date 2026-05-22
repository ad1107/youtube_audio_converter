from dataclasses import dataclass

# ── Dependency Check ─────────────────────────────────────────────────────────

from yt_dlp.version import __version__ as YTDLP_VERSION

# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PlaylistJob:
    url: str
    output_dir: str
    fmt: str
    quality: str
    job_id: int
    label: str | None      = None
    speed: float          = 1.0
    volume: float         = 1.0
    playlist_title: str   = "Fetching..."
    total_videos: int     = 0
    completed_videos: int = 0
    failed_videos: int    = 0
    status: str           = "pending"
    error_msg: str        = ""
    start_time: float     = 0.0
    end_time: float       = 0.0
    output_folder: str    = ""
    _last_prog_log: float  = 0.0
    _last_ffmpeg_prog_log: float = 0.0

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
