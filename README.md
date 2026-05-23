# YouTube Audio/Video Converter

Download YouTube videos, single tracks, playlists, audiobooks, podcasts, and music compilations from a GUI or CLI. The app can convert downloads into audio files for music libraries, keep video files in common containers, embed metadata and artwork when the target format supports it, and resume playlist updates without downloading files that already exist.

## Highlights

- Audio output: M4A/AAC, HE-AAC Mono, MP3, Opus, FLAC, ALAC, WAV, AIFF.
- Video output: MP4, MKV, WebM.
- Format-specific quality presets instead of one shared quality list.
- Separate concurrent download and concurrent FFmpeg conversion limits.
- Track-level concurrency, including entries inside playlists.
- Download start delay, defaulting to 10 seconds, to avoid starting every request at once.
- Skip Existing support for playlist updates and re-runs.
- Retry Errors button for failed items.
- GUI Progress View with one active progress bar per downloading or converting item.
- GUI Log View with save, clear, auto-scroll, and JavaScript warning suppression controls.
- Optional playback speed and volume filters for audio output.
- Cookie file, browser-cookie, and optional Deno support for YouTube access issues.
- Local FFmpeg and Deno dependency download helpers.

## Typical Uses

- Convert a long audiobook playlist to compact HE-AAC Mono.
- Convert music playlists to M4A, MP3, Opus, FLAC, or ALAC.
- Keep a podcast playlist updated by re-running the same source with Skip Existing enabled.
- Download a YouTube video as MP4, MKV, or WebM.
- Batch several single videos and playlists from a text file.

## Install

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install FFmpeg through the app helper:

```powershell
python main.py --cli --download-dependencies ffmpeg
```

Optional Deno install for yt-dlp remote components:

```powershell
python main.py --cli --download-dependencies deno
```

## Run The GUI

```powershell
python main.py
```

or:

```powershell
python -m youtube_audio_converter
```

The GUI places URLs, output folder, and settings on the left. Progress View and Log View are on the right. Start Download, Stop, Retry Errors, and the post-run power action selector are in the bottom action bar.

## Run From The CLI

List every supported format and valid quality value:

```powershell
python main.py --list-formats
```

Download sources from a text file:

```powershell
python main.py --cli --input sources.txt --output D:\Downloads\Media --concurrent-downloads 3 --concurrent-converts 1
```

Download one video as compact speech audio:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=wzE0qslqRAw" --format he-aac --quality 64 --volume 1.2
```

Download one video as MP4 capped at 1080p:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=wzE0qslqRAw" --format mp4 --quality 1080
```

Download with cookies from a browser:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=XmB3hWRszBs" --cookies-from-browser chrome
```

Download with cookies and Deno enabled:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=wzE0qslqRAw" --cookies-from-browser firefox --use-deno
```

## Source Text Files

Each non-empty line is one job.

Use either:

```text
Playlist folder | https://www.youtube.com/playlist?list=...
https://www.youtube.com/watch?v=...
```

If a folder label is omitted, the app uses the playlist title when available, or a sanitized fallback.

## Formats And Quality Values

| Format | Output | Type | Quality values |
| --- | --- | --- | --- |
| `m4a` | `.m4a` | audio | `best`, `320`, `256`, `192`, `128` |
| `he-aac` | `.m4a` | audio | `96`, `64`, `32`, `24` |
| `mp3` | `.mp3` | audio | `best`, `320`, `256`, `192`, `128` |
| `opus` | `.opus` | audio | `160`, `128`, `96`, `64` |
| `flac` | `.flac` | audio | `lossless` |
| `alac` | `.m4a` | audio | `lossless` |
| `wav` | `.wav` | audio | `lossless` |
| `aiff` | `.aiff` | audio | `lossless` |
| `mp4` | `.mp4` | video | `best`, `2160`, `1440`, `1080`, `720`, `480`, `360` |
| `mkv` | `.mkv` | video | `best`, `2160`, `1440`, `1080`, `720`, `480`, `360` |
| `webm` | `.webm` | video | `best`, `2160`, `1440`, `1080`, `720`, `480`, `360` |

Audio speed and volume filters apply to audio formats. They are ignored for video formats.

## Concurrency

Downloads are scheduled at the item level. A 300-track playlist can download multiple tracks at once instead of waiting for each track to finish before starting the next.

CLI controls:

```powershell
--concurrent-downloads 3
--concurrent-converts 1
--download-start-delay 10
```

The download start delay is a cooldown between new download starts. Existing files are checked before queueing downloads, so Skip Existing can move through old playlist items quickly.

## Authentication

If YouTube asks for sign-in or shows a bot check, use one of:

```powershell
--cookiefile C:\path\to\cookies.txt
--cookies-from-browser chrome
--cookies-from-browser "firefox:default"
--use-deno
```

In the GUI, use Cookies File or Browser Cookies. If both are set, the cookie file wins.

## Project Layout

- `main.py` is a compatibility launcher.
- `youtube_audio_converter/entrypoint.py` selects GUI or CLI mode.
- `youtube_audio_converter/cli.py` owns CLI parsing and batch execution.
- `youtube_audio_converter/gui/` contains the Tkinter app, layout, settings, log view, progress view, and GUI download controller.
- `youtube_audio_converter/core/` contains download orchestration, format definitions, path planning, postprocessor construction, FFmpeg progress parsing, yt-dlp options, URL parsing, cookies, and runtime concurrency gates.
- `youtube_audio_converter/dependencies.py` handles FFmpeg and Deno discovery/download helpers.

## Notes

This project prepares media files and folders. It does not import files into Apple Music, iTunes, 3uTools, or any phone manager.
