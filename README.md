# Music Audiobook Importer

> **Do you have an hours-long audiobook, a massive music compilation, or a lengthy podcast on YouTube that you want to listen to offline on your phone?** 

This application makes it incredibly easy! It downloads one or more YouTube video or playlist URLs, extracts the audio with optional custom speed adjustments (perfect for listening at 1.3x speed!), and neatly organizes the results into separate folders. Along the way, it automatically embeds cover art and metadata, making your files perfectly ready to drop straight into Apple Music, iTunes, or your favorite mobile player.

It is designed for a workflow like:

1. Put several playlist URLs into the app.
2. Download each playlist into its own folder.
3. Convert each video to `.m4a` with embedded metadata and thumbnail art.
4. Import the resulting files into Apple Music by your preferred transfer method.

## What it produces

The default output is:

- `.m4a` audio files
- embedded metadata when ffmpeg can write it
- embedded thumbnail art when ffmpeg/AtomicParsley supports it
- folder-per-playlist organization

## Apple-friendly formats

Apple Music and the Music app are safest with `.m4a` / AAC. The app can also work with other common formats such as MP3, WAV, AIFF, and Apple Lossless, but `.m4a` is the most practical default for YouTube audiobook downloads.

## Source line format

Each non-empty line is one job.

Use either:

- `Playlist folder | https://www.youtube.com/playlist?list=...`
- `https://www.youtube.com/playlist?list=...`

If you omit the folder name, the app uses the playlist title when it can, or a sanitized fallback.

## Run the GUI

```powershell
python main.py
```

## Run from the CLI

```powershell
python main.py --cli --input sources.txt --output D:\Audiobooks --concurrent 3
```

Single URL example:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=wzE0qslqRAw" --format m4a --quality he_24
```

Cookies support:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=XmB3hWRszBs" --cookies-from-browser chrome
```

You can also use a browser profile:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=XmB3hWRszBs" --cookies-from-browser "firefox:default"
```

For the GUI, use either the `Cookies File` picker or the `Browser Cookies` dropdown. If both are set, the file wins.

or:

```powershell
python main.py --cli --url "https://www.youtube.com/watch?v=XmB3hWRszBs" --cookiefile C:\\path\\to\\cookies.txt
```

## Features

- Apple-friendly formats M4A (AAC), MP3, FLAC, ALAC, WAV, AIFF.
- HE-AAC 24kbps Mono - designed for extreme compression of voice and audiobooks (96kbps, 64kbps, 24kbps) natively via iTunes-compatible encoding.
- Automatically prevents your PC from sleeping while downloads are running, and can optionally Sleep, Hibernate, or Shutdown when all jobs are complete.
- **Auto-Fetching FFmpeg**: Bundles FFmpeg and yt-dlp correctly for Windows.
- CLI mode for batch downloads, single URLs, and cookie-based YouTube authentication.

## Requirements

- Python 3.11+
- `yt-dlp`
- `ffmpeg` available on `PATH`

## Notes

This repo does not handle importing into Apple Music or 3uTools. It only prepares the audio files and folder structure.

## Authentication

If YouTube shows a bot-check or sign-in prompt, you can point the app at a `cookies.txt` export or choose a browser session to load cookies from. The cookies file takes priority if both are set.
