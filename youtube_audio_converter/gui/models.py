from youtube_audio_converter.core.formats import format_label_map, quality_label_map


class Theme:
    BG = "#202020"
    BG2 = "#252525"
    BG3 = "#303030"
    BG4 = "#3a3a3a"
    ACCENT = "#0078d4"
    GREEN = "#6ccb5f"
    YELLOW = "#f2c94c"
    RED = "#d83b01"
    PURPLE = "#b69cff"
    TEXT = "#f3f3f3"
    MUTED = "#a7a7a7"
    BORDER = "#454545"
    WHITE = "#ffffff"


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
