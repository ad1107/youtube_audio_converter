from .cli import build_parser, run_cli
from .dependencies import download_ffmpeg_if_needed


def should_use_cli(args) -> bool:
    if args.gui:
        return False
    if getattr(args, "download_dependencies", None):
        return True
    if getattr(args, "list_formats", False):
        return True
    if args.cli:
        return True
    return bool(args.url or args.input)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if should_use_cli(args):
        return run_cli(args)

    from .gui import YoutubeAudioConverter

    app = YoutubeAudioConverter()
    app.show()

    if not download_ffmpeg_if_needed(app.main_window):
        print("WARNING: ffmpeg not found in PATH and could not be downloaded. Audio conversion will fail.")
        app.main_window.log("SYSTEM", "FFmpeg not found and automatic download failed. Audio conversion will fail.", "WARNING")

    app.main_window.refresh_dependencies()
    app.mainloop()
    return 0
