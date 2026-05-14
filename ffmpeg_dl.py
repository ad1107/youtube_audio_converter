import os
import sys
import shutil
import urllib.request
import zipfile
import time
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

def get_local_bin_path() -> Path:
    if getattr(sys, 'frozen', False):
        # Running inside PyInstaller / compiled context
        # Put it strictly in a "bin" folder right next to the .exe file
        return Path(sys.executable).parent / "bin"
    return Path(__file__).parent / "bin"

def get_ffmpeg_path() -> str:
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    local_bin = get_local_bin_path()
    local_ffmpeg = local_bin / "ffmpeg.exe" if sys.platform == "win32" else local_bin / "ffmpeg"
    if local_ffmpeg.exists():
        os.environ["PATH"] = str(local_bin) + os.pathsep + os.environ.get("PATH", "")
        return str(local_ffmpeg)
    return ""

def download_ffmpeg_if_needed(parent=None):
    if get_ffmpeg_path():
        return True
    
    local_bin = get_local_bin_path()
    local_bin.mkdir(parents=True, exist_ok=True)

    popup = tk.Toplevel(parent) if parent else tk.Tk()
    popup.title("Auto-Downloading FFmpeg")
    popup.geometry("380x150")
    if parent:
        popup.transient(parent)
    popup.grab_set()
    popup.focus_force()

    lbl_title = tk.Label(popup, text="Configuring FFmpeg Environment...", font=("Helvetica Neue", 11, "bold"))
    lbl_title.pack(pady=(15, 5))

    progress = ttk.Progressbar(popup, orient="horizontal", length=300, mode="determinate")
    progress.pack(pady=5)

    lbl_status = tk.Label(popup, text="Starting download...", font=("Courier New", 9))
    lbl_status.pack(pady=5)

    start_time = [time.time()]

    def reporthook(blocknum, blocksize, totalsize):
        if blocknum == 0:
            start_time[0] = time.time()
            return
        elapsed = time.time() - start_time[0]
        current = blocknum * blocksize
        pct = min(current * 100.0 / totalsize, 100) if totalsize > 0 else 0
        
        avg_speed = (current / elapsed) if elapsed > 0 else 0
        
        downloaded_mb = current / (1024 * 1024)
        total_mb = totalsize / (1024 * 1024) if totalsize > 0 else 0
        
        if avg_speed >= 1024 * 1024:
            speed_str = f"{avg_speed/(1024*1024):.1f} MB/s"
        else:
            speed_str = f"{avg_speed/1024:.1f} KB/s"
            
        lbl_status.config(text=f"{pct:.0f}% | {downloaded_mb:.1f}/{total_mb:.1f}MB | {speed_str}")
        progress["value"] = pct
        popup.update()

    try:
        popup.update()
        if sys.platform == "win32":
            import subprocess
            import json

            # Step 1: Download 7zr.exe (standalone, no extraction needed)
            lbl_status.config(text="Fetching extractor...")
            popup.update()
            sza_path = local_bin / "7zr.exe"
            urllib.request.urlretrieve(
                "https://github.com/ip7z/7zip/releases/download/26.01/7zr.exe",
                sza_path
            )

            # Step 2: Resolve latest ffmpeg-autobuild release URL dynamically
            lbl_status.config(text="Resolving latest FFmpeg build...")
            popup.update()
            api_url = "https://api.github.com/repos/AnimMouse/ffmpeg-autobuild/releases/latest"
            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r:
                release = json.loads(r.read())
            asset = next(a for a in release["assets"] if "win64-nonfree" in a["name"])
            url = asset["browser_download_url"]

            # Step 3: Download the archive
            archive_path = local_bin / "ffmpeg.7z"
            urllib.request.urlretrieve(url, archive_path, reporthook)

            # Step 4: Extract ffmpeg.exe and ffprobe.exe
            lbl_status.config(text="Extracting archive...")
            popup.update()
            subprocess.run(
                [str(sza_path), "e", str(archive_path), "-o" + str(local_bin), "*.exe", "-r", "-y"],
                check=True, capture_output=True
            )

            # Cleanup
            archive_path.unlink()
            sza_path.unlink()
        elif sys.platform == "darwin":
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            zip_path = local_bin / "ffmpeg.zip"
            urllib.request.urlretrieve(url, zip_path, reporthook)
            lbl_status.config(text="Extracting archive...")
            popup.update()
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(local_bin)
            zip_path.unlink()
            (local_bin / "ffmpeg").chmod(0o755)
        else:
            import tarfile
            url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            tar_path = local_bin / "ffmpeg.tar.xz"
            urllib.request.urlretrieve(url, tar_path, reporthook)
            lbl_status.config(text="Extracting archive...")
            popup.update()
            with tarfile.open(tar_path, "r:xz") as t:
                for member in t.getmembers():
                    if member.name.endswith("ffmpeg") or member.name.endswith("ffprobe"):
                        member.name = Path(member.name).name
                        t.extract(member, local_bin)
            tar_path.unlink()
            (local_bin / "ffmpeg").chmod(0o755)
            
        os.environ["PATH"] = str(local_bin) + os.pathsep + os.environ.get("PATH", "")
        time.sleep(0.3)
        popup.destroy()
        return True
    except Exception as e:
        messagebox.showerror("FFmpeg Download Error", f"Failed to download FFmpeg:\n{e}", parent=popup)
        popup.destroy()
        return False