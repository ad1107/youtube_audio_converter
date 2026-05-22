import copy
import os
from pathlib import Path

import yt_dlp
from yt_dlp.postprocessor import ffmpeg as yt_ffmpeg
from yt_dlp.utils import sanitize_filename


FINAL_EXTENSIONS = {
    "alac": "m4a",
    "aiff": "aiff",
    "m4a": "m4a",
    "mp3": "mp3",
    "flac": "flac",
    "wav": "wav",
}


def ensure_audio_codec_support() -> None:
    """Patch small gaps in yt-dlp's FFmpegExtractAudio table."""
    if "aiff" not in yt_ffmpeg.ACODECS:
        yt_ffmpeg.ACODECS["aiff"] = ("aiff", None, ("-f", "aiff", "-acodec", "pcm_s16be"))
    if "aiff" not in yt_ffmpeg.FFmpegExtractAudioPP.SUPPORTED_EXTS:
        yt_ffmpeg.FFmpegExtractAudioPP.SUPPORTED_EXTS = (
            *yt_ffmpeg.FFmpegExtractAudioPP.SUPPORTED_EXTS,
            "aiff",
        )


def final_audio_ext(fmt: str) -> str:
    return FINAL_EXTENSIONS.get(fmt, fmt)


def safe_folder_name(value: str, fallback: str = "YouTube Audio") -> str:
    cleaned = sanitize_filename((value or "").strip(), restricted=False).strip(" .")
    return cleaned or fallback


def safe_file_stem(value: str, fallback: str) -> str:
    cleaned = sanitize_filename((value or "").strip(), restricted=False).strip(" .")
    return (cleaned or fallback).replace("%", "%%")


def build_postprocessors(
    fmt: str,
    quality: str,
    speed: float,
    embed_thumbnail: bool,
    crop_thumb: bool,
    embed_metadata: bool,
    skip_existing: bool = True,
):
    ensure_audio_codec_support()
    is_he_aac = quality.startswith("he_")
    is_lossless = fmt in ["flac", "wav", "aiff", "alac"]

    pp_extract = {
        "key": "FFmpegExtractAudio",
        "preferredcodec": fmt,
        "nopostoverwrites": skip_existing,
    }
    if not is_he_aac and not is_lossless:
        pp_extract["preferredquality"] = quality

    postprocessors = [pp_extract]
    if embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
    if embed_thumbnail:
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    postprocessor_args: dict[str, list[str]] = {}
    atempo_filter = _atempo_filter(speed)

    if is_he_aac:
        bitrate = quality.split("_", 1)[1] + "k"
        extract_args = [
            "-c:a",
            "libfdk_aac",
            "-profile:a",
            "aac_he",
            "-b:a",
            bitrate,
            "-ac",
            "1",
            "-ar",
            "44100",
        ]
        if atempo_filter:
            extract_args.extend(["-af", atempo_filter])
        postprocessor_args["extractaudio+ffmpeg_o"] = extract_args
    elif atempo_filter:
        encoder_map = {
            "m4a": "aac",
            "mp3": "libmp3lame",
            "flac": "flac",
            "wav": "pcm_s16le",
            "aiff": "pcm_s16be",
            "alac": "alac",
        }
        postprocessor_args["extractaudio+ffmpeg_o"] = [
            "-c:a",
            encoder_map.get(fmt, "aac"),
            "-af",
            atempo_filter,
        ]

    if embed_thumbnail and crop_thumb:
        crop_vf = "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"
        postprocessor_args["thumbnailsconvertor+ffmpeg_o"] = ["-c:v", "mjpeg", "-vf", crop_vf]

    return postprocessors, postprocessor_args


def _atempo_filter(speed: float) -> str | None:
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = 1.0
    if speed == 1.0:
        return None
    if speed <= 0:
        return None

    factors = []
    remaining = speed
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    while remaining > 100.0:
        factors.append(100.0)
        remaining /= 100.0
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6g}" for factor in factors)


def clone_postprocessors(postprocessors, postprocessor_args):
    return copy.deepcopy(postprocessors), copy.deepcopy(postprocessor_args)


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
    info["ext"] = final_audio_ext(fmt)
    return info


def expected_output_path(outtmpl: str, info: dict, fmt: str) -> str:
    final_ext = final_audio_ext(fmt)
    params = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "final_ext": final_ext,
    }
    with yt_dlp.YoutubeDL(params) as ydl:
        filename = ydl.prepare_filename(filename_info(info, info.get("playlist_title") or "", info.get("playlist_index") or 1, fmt))
    return filename


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
