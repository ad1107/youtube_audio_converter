from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .ffmpeg_progress import FFmpegProgress

if TYPE_CHECKING:
    from .runtime import DownloadRuntime


LogCallback = Callable[[str, str, str], None]


def noop(*args, **kwargs):
    return None


@dataclass
class PlaylistJob:
    url: str
    output_dir: str
    fmt: str
    quality: str
    job_id: int
    label: str | None = None
    speed: float = 1.0
    volume: float = 1.0
    playlist_title: str = "Fetching..."
    total_videos: int = 0
    completed_videos: int = 0
    failed_videos: int = 0
    status: str = "pending"
    error_msg: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    output_folder: str = ""
    _last_prog_log: float = 0.0
    _last_ffmpeg_prog_log: float = 0.0


@dataclass
class DownloadSettings:
    output_dir: str
    fmt: str
    quality: str
    speed: float = 1.0
    volume: float = 1.0
    cookiefile: str = ""
    cookies_browser: str = ""
    use_deno: bool = False
    embed_thumbnail: bool = True
    crop_thumbnail: bool = True
    embed_metadata: bool = True
    track_num: bool = True
    skip_existing: bool = True
    suppress_js_warnings: bool = True
    verbose: bool = False
    max_retries: int = 5
    concurrent_downloads: int = 2
    concurrent_converts: int = 1
    download_start_delay: float = 10.0
    runtime: "DownloadRuntime | None" = field(default=None, repr=False)


@dataclass
class DownloadItem:
    index: int
    title: str
    url: str
    outtmpl: str
    expected_path: str
    duration: float = 0.0
    info: dict = field(default_factory=dict)


@dataclass
class FailedItem:
    title: str
    url: str
    source_url: str
    playlist_title: str
    reason: str = ""
    index: int = 0

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source_url": self.source_url,
            "playlist_title": self.playlist_title,
            "reason": self.reason,
            "index": self.index,
        }


@dataclass
class DownloadCallbacks:
    log: LogCallback = noop
    is_cancelled: Callable[[], bool] = lambda: False
    on_metadata: Callable[[object, str, int, str], None] = noop
    on_item_queued: Callable[[object, DownloadItem, int], None] = noop
    on_item_started: Callable[[object, DownloadItem, int], None] = noop
    on_item_skipped: Callable[[object, DownloadItem, str], None] = noop
    on_item_done: Callable[[object, DownloadItem, str], None] = noop
    on_item_failed: Callable[[object, DownloadItem | None, FailedItem], None] = noop
    on_download_progress: Callable[[object, DownloadItem, dict], None] = noop
    on_postprocessor: Callable[[object, DownloadItem, dict], None] = noop
    on_ffmpeg_progress: Callable[[object, DownloadItem, FFmpegProgress], None] = noop
