import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk


FFMPEG_RELEASE_API = "https://api.github.com/repos/AnimMouse/ffmpeg-autobuild/releases/latest"
SEVEN_Z_URL = "https://github.com/ip7z/7zip/releases/download/26.01/7zr.exe"
DENO_WINDOWS_URL = "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip"


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
    popup = _ProgressPopup(parent, "Auto-Downloading FFmpeg", "Configuring FFmpeg Environment...")
    try:
        if sys.platform == "win32":
            _install_ffmpeg_windows(local_bin, popup)
        elif sys.platform == "darwin":
            _install_ffmpeg_macos(local_bin, popup)
        else:
            _install_ffmpeg_linux(local_bin, popup)

        _prepend_path(local_bin)
        popup.close()
        return True
    except Exception as exc:
        popup.show_error("FFmpeg Download Error", f"Failed to download FFmpeg:\n{exc}")
        return False


def download_deno_if_needed(parent=None):
    if get_deno_path():
        return True

    local_bin = _ensure_local_bin()
    popup = _ProgressPopup(parent, "Downloading Deno", "Setting up Deno Environment...")
    try:
        _install_deno_windows(local_bin, popup)
        popup.close()
        return True
    except Exception as exc:
        popup.show_error("Deno Download Error", f"Failed to download Deno:\n{exc}")
        return False


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


class _ProgressPopup:
    def __init__(self, parent, title: str, heading: str):
        self.popup = tk.Toplevel(parent) if parent else tk.Tk()
        self.popup.title(title)
        self.popup.geometry("380x150")
        if parent:
            self.popup.transient(parent)
        self.popup.grab_set()
        self.popup.focus_force()

        tk.Label(self.popup, text=heading, font=("Helvetica Neue", 11, "bold")).pack(pady=(15, 5))
        self.progress = ttk.Progressbar(self.popup, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(pady=5)
        self.status = tk.Label(self.popup, text="Starting download...", font=("Courier New", 9))
        self.status.pack(pady=5)
        self.start_time = time.time()
        self.popup.update()

    def set_status(self, text: str) -> None:
        self.status.config(text=text)
        self.popup.update()

    def reporthook(self, blocknum, blocksize, totalsize) -> None:
        if blocknum == 0:
            self.start_time = time.time()
            return

        elapsed = max(time.time() - self.start_time, 0.001)
        current = blocknum * blocksize
        percent = min(current * 100.0 / totalsize, 100) if totalsize > 0 else 0
        downloaded_mb = current / (1024 * 1024)
        total_mb = totalsize / (1024 * 1024) if totalsize > 0 else 0
        speed = current / elapsed
        speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed >= 1024 * 1024 else f"{speed / 1024:.1f} KB/s"

        self.status.config(text=f"{percent:.0f}% | {downloaded_mb:.1f}/{total_mb:.1f}MB | {speed_text}")
        self.progress["value"] = percent
        self.popup.update()

    def close(self) -> None:
        time.sleep(0.3)
        self.popup.destroy()

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self.popup)
        self.popup.destroy()


def _download(url: str, target: Path, popup: _ProgressPopup | None = None) -> None:
    hook = popup.reporthook if popup else None
    urllib.request.urlretrieve(url, target, hook)


def _install_ffmpeg_windows(local_bin: Path, popup: _ProgressPopup) -> None:
    popup.set_status("Fetching extractor...")
    sza_path = local_bin / "7zr.exe"
    _download(SEVEN_Z_URL, sza_path)

    popup.set_status("Resolving latest FFmpeg build...")
    req = urllib.request.Request(FFMPEG_RELEASE_API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        release = json.loads(response.read())
    asset = next(item for item in release["assets"] if "win64-nonfree" in item["name"])

    archive_path = local_bin / "ffmpeg.7z"
    _download(asset["browser_download_url"], archive_path, popup)

    popup.set_status("Extracting archive...")
    subprocess.run(
        [str(sza_path), "e", str(archive_path), "-o" + str(local_bin), "*.exe", "-r", "-y"],
        check=True,
        capture_output=True,
        creationflags=_creationflags(),
    )
    archive_path.unlink(missing_ok=True)
    sza_path.unlink(missing_ok=True)


def _install_ffmpeg_macos(local_bin: Path, popup: _ProgressPopup) -> None:
    zip_path = local_bin / "ffmpeg.zip"
    _download("https://evermeet.cx/ffmpeg/getrelease/zip", zip_path, popup)
    popup.set_status("Extracting archive...")
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(local_bin)
    zip_path.unlink(missing_ok=True)
    (local_bin / "ffmpeg").chmod(0o755)


def _install_ffmpeg_linux(local_bin: Path, popup: _ProgressPopup) -> None:
    import tarfile

    tar_path = local_bin / "ffmpeg.tar.xz"
    _download("https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz", tar_path, popup)
    popup.set_status("Extracting archive...")
    with tarfile.open(tar_path, "r:xz") as archive:
        for member in archive.getmembers():
            if member.name.endswith("ffmpeg") or member.name.endswith("ffprobe"):
                member.name = Path(member.name).name
                archive.extract(member, local_bin)
    tar_path.unlink(missing_ok=True)
    (local_bin / "ffmpeg").chmod(0o755)


def _install_deno_windows(local_bin: Path, popup: _ProgressPopup) -> None:
    popup.set_status("Resolving latest Deno build...")
    archive_path = local_bin / "deno.zip"
    _download(DENO_WINDOWS_URL, archive_path, popup)

    popup.set_status("Extracting archive...")
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(local_bin)
    archive_path.unlink(missing_ok=True)
