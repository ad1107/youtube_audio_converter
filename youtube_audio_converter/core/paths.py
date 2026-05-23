from __future__ import annotations

import os
from pathlib import Path

import yt_dlp
from yt_dlp.utils import sanitize_filename

from .formats import final_output_ext


def safe_folder_name(value: str, fallback: str = "YouTube Audio") -> str:
    cleaned = sanitize_filename((value or "").strip(), restricted=False).strip(" .")
    return cleaned or fallback


def safe_file_stem(value: str, fallback: str) -> str:
    cleaned = sanitize_filename((value or "").strip(), restricted=False).strip(" .")
    return (cleaned or fallback).replace("%", "%%")


def output_folder_for(base_dir: str, label: str | None, title: str, job_id: int) -> str:
    folder_name = safe_folder_name(label or title, fallback=f"YouTube Audio {job_id + 1}")
    return str(Path(base_dir) / folder_name)


def item_template(output_folder: str, index: int, track_num: bool, is_playlist: bool, title: str | None = None) -> str:
    if title:
        stem = safe_file_stem(title, fallback=f"Track {index:02d}")
        if track_num and is_playlist:
            filename = f"{index:02d} - {stem}.%(ext)s"
        else:
            filename = f"{stem}.%(ext)s"
        return os.path.join(output_folder, filename)

    if track_num and is_playlist:
        filename = f"{index:02d} - %(title)s.%(ext)s"
    else:
        filename = "%(title)s.%(ext)s"
    return os.path.join(output_folder, filename)


def filename_info(entry: dict, playlist_title: str, index: int, fmt: str) -> dict:
    info = dict(entry or {})
    info["playlist_title"] = info.get("playlist_title") or playlist_title
    info["playlist"] = info.get("playlist") or playlist_title
    info["playlist_index"] = info.get("playlist_index") or index
    info["title"] = info.get("title") or f"Track {index:02d}"
    info["ext"] = final_output_ext(fmt)
    return info


def expected_output_path(outtmpl: str, info: dict, fmt: str) -> str:
    final_ext = final_output_ext(fmt)
    params = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "final_ext": final_ext,
    }
    with yt_dlp.YoutubeDL(params) as ydl:
        prepared_info = filename_info(
            info,
            info.get("playlist_title") or "",
            info.get("playlist_index") or 1,
            fmt,
        )
        return ydl.prepare_filename(prepared_info)


def existing_output_path(outtmpl: str, info: dict, fmt: str) -> str:
    expected = expected_output_path(outtmpl, info, fmt)
    if expected and os.path.isfile(expected) and os.path.getsize(expected) > 0:
        return expected
    return ""


def item_url(entry: dict, source_url: str) -> str:
    value = (
        entry.get("webpage_url")
        or entry.get("original_url")
        or entry.get("url")
        or source_url
    )
    value = str(value)
    if value.startswith("http"):
        return value
    video_id = entry.get("id") or value
    return f"https://www.youtube.com/watch?v={video_id}"
