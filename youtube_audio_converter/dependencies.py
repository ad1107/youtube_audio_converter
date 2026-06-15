import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Protocol


FFMPEG_RELEASE_API = "https://api.github.com/repos/AnimMouse/ffmpeg-autobuild/releases/latest"
SEVEN_Z_URL = "https://github.com/ip7z/7zip/releases/download/26.01/7zr.exe"
DENO_WINDOWS_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"


class ProgressReporter(Protocol):
    def set_status(self, text: str) -> None:
        ...

    def reporthook(self, blocknum, blocksize, totalsize) -> None:
        ...

    def close(self) -> None:
        ...

    def show_error(self, title: str, message: str) -> None:
        ...


def get_local_bin_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "bin"
    return Path(__file__).resolve().parent.parent / "bin"


def get_ffmpeg_path() -> str:
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    local_ffmpeg = _local_executable("ffmpeg")
    if local_ffmpeg.exists():
        _prepend_path(local_ffmpeg.parent)
        return str(local_ffmpeg)
    return ""


def get_deno_path() -> str:
    local_deno = _local_executable("deno")
    if local_deno.exists():
        return str(local_deno)

    sys_deno = shutil.which("deno")
    if sys_deno:
        return sys_deno
    return ""


def download_ffmpeg_if_needed(parent=None):
    if get_ffmpeg_path():
        return True

    local_bin = _ensure_local_bin()
    progress = _progress_reporter(parent, "Auto-Downloading FFmpeg", "Configuring FFmpeg Environment...")
    try:
        if sys.platform == "win32":
            _install_ffmpeg_windows(local_bin, progress)
        elif sys.platform == "darwin":
            _install_ffmpeg_macos(local_bin, progress)
        else:
            _install_ffmpeg_linux(local_bin, progress)

        _prepend_path(local_bin)
        progress.close()
        return True
    except Exception as exc:
        progress.show_error("FFmpeg Download Error", f"Failed to download FFmpeg:\n{exc}")
        return False


def download_deno_if_needed(parent=None):
    if get_deno_path():
        return True

    local_bin = _ensure_local_bin()
    progress = _progress_reporter(parent, "Downloading Deno", "Setting up Deno Environment...")
    try:
        _install_deno_windows(local_bin, progress)
        progress.close()
        return True
    except Exception as exc:
        progress.show_error("Deno Download Error", f"Failed to download Deno:\n{exc}")
        return False


def _progress_reporter(parent, title: str, heading: str) -> ProgressReporter:
    factory = getattr(parent, "create_progress_reporter", None)
    if callable(factory):
        return factory(title, heading)
    return _ConsoleProgress(title, heading)


def _local_executable(name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return get_local_bin_path() / f"{name}{suffix}"


def _ensure_local_bin() -> Path:
    local_bin = get_local_bin_path()
    local_bin.mkdir(parents=True, exist_ok=True)
    return local_bin


def _prepend_path(path: Path) -> None:
    path_text = str(path)
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if path_text not in parts:
        os.environ["PATH"] = path_text + os.pathsep + os.environ.get("PATH", "")


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class _ConsoleProgress:
    def __init__(self, title: str, heading: str):
        self.title = title
        self.heading = heading
        self.start_time = time.time()
        self.last_report = 0.0
        print(f"[INFO] {title}: {heading}", flush=True)

    def set_status(self, text: str) -> None:
        print(f"[INFO] {text}", flush=True)

    def reporthook(self, blocknum, blocksize, totalsize) -> None:
        if blocknum == 0:
            self.start_time = time.time()
            self.last_report = 0.0
            return

        now = time.time()
        if now - self.last_report < 0.75:
            return
        self.last_report = now

        elapsed = max(now - self.start_time, 0.001)
        current = blocknum * blocksize
        percent = min(current * 100.0 / totalsize, 100) if totalsize > 0 else 0
        downloaded_mb = current / (1024 * 1024)
        total_mb = totalsize / (1024 * 1024) if totalsize > 0 else 0
        speed = current / elapsed
        speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.1f} KB/s"
        if totalsize > 0:
            print(f"[INFO] {percent:.0f}% | {downloaded_mb:.1f}/{total_mb:.1f} MB | {speed_text}", flush=True)
        else:
            print(f"[INFO] {downloaded_mb:.1f} MB | {speed_text}", flush=True)

    def close(self) -> None:
        return None

    def show_error(self, title: str, message: str) -> None:
        print(f"[ERROR] {title}: {message}", file=sys.stderr, flush=True)


def _download(url: str, target: Path, progress: ProgressReporter | None = None) -> None:
    hook = progress.reporthook if progress else None
    urllib.request.urlretrieve(url, target, hook)


def _install_ffmpeg_windows(local_bin: Path, progress: ProgressReporter) -> None:
    progress.set_status("Fetching extractor...")
    sza_path = local_bin / "7zr.exe"
    _download(SEVEN_Z_URL, sza_path)

    progress.set_status("Resolving latest FFmpeg build...")
    req = urllib.request.Request(FFMPEG_RELEASE_API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        release = json.loads(response.read())
    asset = next(item for item in release["assets"] if "win64-nonfree" in item["name"])

    archive_path = local_bin / "ffmpeg.7z"
    _download(asset["browser_download_url"], archive_path, progress)

    progress.set_status("Extracting archive...")
    subprocess.run(
        [str(sza_path), "e", str(archive_path), "-o" + str(local_bin), "*.exe", "-r", "-y"],
        check=True,
        capture_output=True,
        creationflags=_creationflags(),
    )
    archive_path.unlink(missing_ok=True)
    sza_path.unlink(missing_ok=True)


def _install_ffmpeg_macos(local_bin: Path, progress: ProgressReporter) -> None:
    zip_path = local_bin / "ffmpeg.zip"
    _download("https://evermeet.cx/ffmpeg/getrelease/zip", zip_path, progress)
    progress.set_status("Extracting archive...")
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(local_bin)
    zip_path.unlink(missing_ok=True)
    (local_bin / "ffmpeg").chmod(0o755)


def _install_ffmpeg_linux(local_bin: Path, progress: ProgressReporter) -> None:
    import tarfile

    tar_path = local_bin / "ffmpeg.tar.xz"
    _download("https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz", tar_path, progress)
    progress.set_status("Extracting archive...")
    with tarfile.open(tar_path, "r:xz") as archive:
        for member in archive.getmembers():
            if member.name.endswith("ffmpeg") or member.name.endswith("ffprobe"):
                member.name = Path(member.name).name
                archive.extract(member, local_bin)
    tar_path.unlink(missing_ok=True)
    (local_bin / "ffmpeg").chmod(0o755)


def _install_deno_windows(local_bin: Path, progress: ProgressReporter) -> None:
    progress.set_status("Resolving latest Deno build...")
    archive_path = local_bin / "deno.zip"
    _download(DENO_WINDOWS_URL, archive_path, progress)

    progress.set_status("Extracting archive...")
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(local_bin)
    archive_path.unlink(missing_ok=True)
