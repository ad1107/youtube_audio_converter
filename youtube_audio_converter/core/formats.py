from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MediaKind = Literal["audio", "video"]


@dataclass(frozen=True)
class QualityOption:
    label: str
    value: str
    ffmpeg_quality: str | None = None
    height: int | None = None
    bitrate: str | None = None


@dataclass(frozen=True)
class FormatSpec:
    code: str
    label: str
    media_kind: MediaKind
    final_ext: str
    quality_options: tuple[QualityOption, ...]
    extract_codec: str | None = None
    audio_encoder: str | None = None
    lossless: bool = False
    mono: bool = False
    merge_output_format: str | None = None
    supports_thumbnail: bool = True
    supports_audio_filters: bool = True

    @property
    def default_quality(self) -> QualityOption:
        return self.quality_options[0]


AAC_QUALITY = (
    QualityOption("Best available", "best", ffmpeg_quality="0"),
    QualityOption("320 kbps", "320", ffmpeg_quality="320", bitrate="320k"),
    QualityOption("256 kbps", "256", ffmpeg_quality="256", bitrate="256k"),
    QualityOption("192 kbps", "192", ffmpeg_quality="192", bitrate="192k"),
    QualityOption("128 kbps", "128", ffmpeg_quality="128", bitrate="128k"),
)
MP3_QUALITY = AAC_QUALITY
OPUS_QUALITY = (
    QualityOption("160 kbps", "160", ffmpeg_quality="160", bitrate="160k"),
    QualityOption("128 kbps", "128", ffmpeg_quality="128", bitrate="128k"),
    QualityOption("96 kbps", "96", ffmpeg_quality="96", bitrate="96k"),
    QualityOption("64 kbps", "64", ffmpeg_quality="64", bitrate="64k"),
)
HE_AAC_QUALITY = (
    QualityOption("96 kbps mono", "96", bitrate="96k"),
    QualityOption("64 kbps mono", "64", bitrate="64k"),
    QualityOption("32 kbps mono", "32", bitrate="32k"),
    QualityOption("24 kbps mono", "24", bitrate="24k"),
)
LOSSLESS_QUALITY = (QualityOption("Lossless", "lossless"),)
VIDEO_QUALITY = (
    QualityOption("Best available", "best"),
    QualityOption("2160p", "2160", height=2160),
    QualityOption("1440p", "1440", height=1440),
    QualityOption("1080p", "1080", height=1080),
    QualityOption("720p", "720", height=720),
    QualityOption("480p", "480", height=480),
    QualityOption("360p", "360", height=360),
)


FORMAT_SPECS: dict[str, FormatSpec] = {
    spec.code: spec
    for spec in (
        FormatSpec(
            code="m4a",
            label="M4A / AAC (Apple Music recommended)",
            media_kind="audio",
            final_ext="m4a",
            quality_options=AAC_QUALITY,
            extract_codec="m4a",
            audio_encoder="aac",
        ),
        FormatSpec(
            code="he-aac",
            label="HE-AAC Mono (speech)",
            media_kind="audio",
            final_ext="m4a",
            quality_options=HE_AAC_QUALITY,
            extract_codec="m4a",
            audio_encoder="libfdk_aac",
            mono=True,
        ),
        FormatSpec(
            code="mp3",
            label="MP3",
            media_kind="audio",
            final_ext="mp3",
            quality_options=MP3_QUALITY,
            extract_codec="mp3",
            audio_encoder="libmp3lame",
        ),
        FormatSpec(
            code="opus",
            label="Opus",
            media_kind="audio",
            final_ext="opus",
            quality_options=OPUS_QUALITY,
            extract_codec="opus",
            audio_encoder="libopus",
        ),
        FormatSpec(
            code="flac",
            label="FLAC (lossless)",
            media_kind="audio",
            final_ext="flac",
            quality_options=LOSSLESS_QUALITY,
            extract_codec="flac",
            audio_encoder="flac",
            lossless=True,
        ),
        FormatSpec(
            code="alac",
            label="ALAC / Apple Lossless",
            media_kind="audio",
            final_ext="m4a",
            quality_options=LOSSLESS_QUALITY,
            extract_codec="alac",
            audio_encoder="alac",
            lossless=True,
        ),
        FormatSpec(
            code="wav",
            label="WAV (uncompressed)",
            media_kind="audio",
            final_ext="wav",
            quality_options=LOSSLESS_QUALITY,
            extract_codec="wav",
            audio_encoder="pcm_s16le",
            lossless=True,
            supports_thumbnail=False,
        ),
        FormatSpec(
            code="aiff",
            label="AIFF (uncompressed)",
            media_kind="audio",
            final_ext="aiff",
            quality_options=LOSSLESS_QUALITY,
            extract_codec="aiff",
            audio_encoder="pcm_s16be",
            lossless=True,
            supports_thumbnail=False,
        ),
        FormatSpec(
            code="mp4",
            label="MP4 video",
            media_kind="video",
            final_ext="mp4",
            quality_options=VIDEO_QUALITY,
            merge_output_format="mp4",
            supports_thumbnail=False,
            supports_audio_filters=False,
        ),
        FormatSpec(
            code="mkv",
            label="MKV video",
            media_kind="video",
            final_ext="mkv",
            quality_options=VIDEO_QUALITY,
            merge_output_format="mkv",
            supports_thumbnail=False,
            supports_audio_filters=False,
        ),
        FormatSpec(
            code="webm",
            label="WebM video",
            media_kind="video",
            final_ext="webm",
            quality_options=VIDEO_QUALITY,
            merge_output_format="webm",
            supports_thumbnail=False,
            supports_audio_filters=False,
        ),
    )
}


def format_codes() -> tuple[str, ...]:
    return tuple(FORMAT_SPECS)


def format_label_map() -> dict[str, str]:
    return {spec.label: spec.code for spec in FORMAT_SPECS.values()}


def get_format_spec(fmt: str) -> FormatSpec:
    return FORMAT_SPECS.get(str(fmt or "").lower(), FORMAT_SPECS["m4a"])


def final_output_ext(fmt: str) -> str:
    return get_format_spec(fmt).final_ext


def supports_thumbnail(fmt: str) -> bool:
    return get_format_spec(fmt).supports_thumbnail


def supports_audio_filters(fmt: str) -> bool:
    return get_format_spec(fmt).supports_audio_filters


def quality_options_for_format(fmt: str) -> tuple[QualityOption, ...]:
    return get_format_spec(fmt).quality_options


def quality_label_map(fmt: str) -> dict[str, str]:
    return {option.label: option.value for option in quality_options_for_format(fmt)}


def quality_labels_for_format(fmt: str) -> list[str]:
    return [option.label for option in quality_options_for_format(fmt)]


def get_quality_option(fmt: str, quality: str | None) -> QualityOption:
    normalized = normalize_quality(fmt, quality)
    for option in quality_options_for_format(fmt):
        if option.value == normalized:
            return option
    return get_format_spec(fmt).default_quality


def normalize_quality(fmt: str, quality: str | None) -> str:
    spec = get_format_spec(fmt)
    if quality is None or str(quality).strip() == "":
        return spec.default_quality.value

    raw = str(quality).strip()
    lowered = raw.lower().replace("kbps", "").strip()
    lowered = lowered.removesuffix("p").strip() if lowered[:-1].isdigit() else lowered
    compact = raw.lower().replace(" ", "")

    if spec.lossless and lowered in {"best", "0"}:
        return spec.default_quality.value

    for option in spec.quality_options:
        label = option.label.lower()
        candidates = {
            option.value.lower(),
            label,
            label.replace(" ", ""),
            label.replace("kbps", "").strip(),
            label.replace("kbps", "").replace(" ", ""),
        }
        if option.ffmpeg_quality:
            candidates.add(option.ffmpeg_quality.lower())
        if option.height:
            candidates.add(str(option.height))
            candidates.add(f"{option.height}p")
        if lowered in candidates or raw.lower() in candidates or compact in candidates:
            return option.value

    values = ", ".join(option.value for option in spec.quality_options)
    raise ValueError(f"{raw!r} is not valid for {spec.code}. Valid qualities: {values}")


def format_quality_summary(fmt: str, quality: str | None) -> str:
    spec = get_format_spec(fmt)
    option = get_quality_option(fmt, quality)
    return f"{spec.label} @ {option.label}"


def ydl_format_selector(fmt: str, quality: str | None) -> str:
    spec = get_format_spec(fmt)
    option = get_quality_option(fmt, quality)

    if spec.media_kind == "audio":
        return "bestaudio/best"

    if spec.code == "mp4":
        if option.height:
            return (
                f"bv*[height<={option.height}][ext=mp4]+ba[ext=m4a]/"
                f"b[height<={option.height}][ext=mp4]/"
                f"bv*[height<={option.height}]+ba/best[height<={option.height}]/best"
            )
        return "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/best"

    if spec.code == "webm":
        if option.height:
            return (
                f"bv*[height<={option.height}][ext=webm]+ba[ext=webm]/"
                f"b[height<={option.height}][ext=webm]/"
                f"bv*[height<={option.height}]+ba/best[height<={option.height}]/best"
            )
        return "bv*[ext=webm]+ba[ext=webm]/b[ext=webm]/bv*+ba/best"

    if option.height:
        return f"bv*[height<={option.height}]+ba/b[height<={option.height}]/best[height<={option.height}]/best"
    return "bv*+ba/best"
