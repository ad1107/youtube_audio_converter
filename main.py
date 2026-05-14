from gui import YoutubeAudioConverter
from ffmpeg_dl import download_ffmpeg_if_needed

def main() -> int:
    if not download_ffmpeg_if_needed():
        print('WARNING: ffmpeg not found in PATH and could not be downloaded. Audio conversion will fail.')
    
    app = YoutubeAudioConverter()
    app.mainloop()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
