from __future__ import annotations

from yt_dlp.postprocessor import ffmpeg as yt_ffmpeg

from .formats import get_format_spec, get_quality_option


def ensure_audio_codec_support() -> None:
    """Patch yt-dlp's extract-audio table for formats it can mux through FFmpeg."""
    if "aiff" not in yt_ffmpeg.ACODECS:
        yt_ffmpeg.ACODECS["aiff"] = ("aiff", None, ("-f", "aiff", "-acodec", "pcm_s16be"))
    if "aiff" not in yt_ffmpeg.FFmpegExtractAudioPP.SUPPORTED_EXTS:
        yt_ffmpeg.FFmpegExtractAudioPP.SUPPORTED_EXTS = (
            *yt_ffmpeg.FFmpegExtractAudioPP.SUPPORTED_EXTS,
            "aiff",
        )


def build_postprocessors(
    fmt: str,
    quality: str,
    speed: float,
    volume: float,
    embed_thumbnail: bool,
    crop_thumb: bool,
    embed_metadata: bool,
    skip_existing: bool = True,
):
    ensure_audio_codec_support()
    spec = get_format_spec(fmt)
    quality_option = get_quality_option(fmt, quality)

    postprocessors = []
    postprocessor_args: dict[str, list[str]] = {}

    if spec.media_kind == "audio":
        pp_extract = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": spec.extract_codec or spec.code,
            "nopostoverwrites": skip_existing,
        }
        if quality_option.ffmpeg_quality and not spec.lossless and spec.code != "he-aac":
            pp_extract["preferredquality"] = quality_option.ffmpeg_quality
        postprocessors.append(pp_extract)

        extract_args = _extract_audio_args(spec.code, quality, speed, volume)
        if extract_args:
            postprocessor_args["extractaudio+ffmpeg_o"] = extract_args

    if embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

    if spec.media_kind == "audio" and embed_thumbnail and spec.supports_thumbnail:
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    if spec.media_kind == "audio" and embed_thumbnail and crop_thumb and spec.supports_thumbnail:
        crop_vf = "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'"
        postprocessor_args["thumbnailsconvertor+ffmpeg_o"] = ["-c:v", "mjpeg", "-vf", crop_vf]

    return postprocessors, postprocessor_args


def _extract_audio_args(fmt: str, quality: str, speed: float, volume: float) -> list[str]:
    spec = get_format_spec(fmt)
    quality_option = get_quality_option(fmt, quality)
    audio_filter = _audio_filter(speed, volume) if spec.supports_audio_filters else None

    if spec.code == "he-aac":
        args = [
            "-c:a",
            spec.audio_encoder or "libfdk_aac",
            "-profile:a",
            "aac_he",
            "-b:a",
            quality_option.bitrate or f"{quality_option.value}k",
            "-ac",
            "1",
            "-ar",
            "44100",
        ]
        if audio_filter:
            args.extend(["-af", audio_filter])
        return args

    if not audio_filter:
        return []

    args = ["-c:a", spec.audio_encoder or "aac"]
    if quality_option.bitrate and not spec.lossless:
        args.extend(["-b:a", quality_option.bitrate])
    args.extend(["-af", audio_filter])
    return args


def _atempo_filter(speed: float) -> str | None:
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = 1.0
    if speed <= 0 or speed == 1.0:
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


def _audio_filter(speed: float, volume: float) -> str | None:
    filters = []
    atempo = _atempo_filter(speed)
    if atempo:
        filters.extend(atempo.split(","))

    try:
        volume = float(volume)
    except (TypeError, ValueError):
        volume = 1.0
    if volume > 0 and abs(volume - 1.0) > 0.000001:
        filters.append(f"volume={volume:.6g}")

    return ",".join(filters) if filters else None
