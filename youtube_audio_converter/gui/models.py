from youtube_audio_converter.core.formats import format_label_map, quality_label_map


class Theme:
    BG = "#0d1117"
    BG2 = "#161b22"
    BG3 = "#21262d"
    BG4 = "#30363d"
    ACCENT = "#58a6ff"
    GREEN = "#3fb950"
    YELLOW = "#d29922"
    RED = "#f85149"
    PURPLE = "#bc8cff"
    TEXT = "#c9d1d9"
    MUTED = "#6e7681"
    BORDER = "#30363d"
    WHITE = "#f0f6fc"


LOG_COLOURS = {
    "INFO": Theme.TEXT,
    "SUCCESS": Theme.GREEN,
    "WARNING": Theme.YELLOW,
    "ERROR": Theme.RED,
    "DEBUG": Theme.MUTED,
    "PROGRESS": Theme.ACCENT,
    "SYSTEM": Theme.PURPLE,
}

FORMATS = format_label_map()
QUALITIES = quality_label_map("m4a")
