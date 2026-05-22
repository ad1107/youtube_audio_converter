def fmt_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        seconds = 0
    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fmt_speed(bytes_per_second: float | int | None) -> str:
    if not bytes_per_second:
        return "..."
    value = float(bytes_per_second)
    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.1f} MB/s"
    if value >= 1024:
        return f"{value / 1024:.1f} KB/s"
    return f"{value:.0f} B/s"
