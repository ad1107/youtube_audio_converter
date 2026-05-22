from pathlib import Path
from urllib.parse import parse_qs, urlparse


def detect_no_playlist(url: str) -> bool:
    """
    Return True for a single video and False for a playlist.

    YouTube watch URLs with a list= parameter are treated as playlists so an
    audiobook playlist can be resumed from a copied episode URL.
    """
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


def url_kind_label(url: str) -> str:
    return "single video" if detect_no_playlist(url) else "playlist"


def parse_source_line(line: str):
    text = line.strip().lstrip("\ufeff")
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


def load_sources(urls, input_files):
    items = []
    for value in urls or []:
        text = value.strip()
        if text:
            items.append((None, text))
    for file_path in input_files or []:
        path = Path(file_path)
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = parse_source_line(line)
            if parsed:
                items.append(parsed)
    return items
