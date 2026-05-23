POSTPROCESSOR_LABELS = {
    "ExtractAudio": "Extracting audio with FFmpeg",
    "Merger": "Muxing video and audio",
    "VideoConvertor": "Converting video container",
    "Metadata": "Writing metadata tags",
    "ThumbnailsConvertor": "Converting artwork to JPEG",
    "EmbedThumbnail": "Embedding artwork into file",
    "MoveFiles": "Moving final file",
}

PROGRESS_POSTPROCESSORS = {"ExtractAudio", "Merger", "VideoConvertor"}
FINALIZING_POSTPROCESSORS = {"Metadata", "ThumbnailsConvertor", "EmbedThumbnail", "MoveFiles"}


def postprocessor_label(name: str) -> str:
    return POSTPROCESSOR_LABELS.get(name, f"Post-processing: {name}")
