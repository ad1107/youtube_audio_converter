from .cli import build_parser, run_cli
from .dependencies import download_ffmpeg_if_needed
from .gui import YoutubeAudioConverter


def should_use_cli(args) -> bool:
    if args.gui:
        return False
    if getattr(args, "download_dependencies", None):
        return True
    if args.cli:
        return True
    return bool(args.url or args.input)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if should_use_cli(args):
        return run_cli(args)

    if not download_ffmpeg_if_needed():
        print("WARNING: ffmpeg not found in PATH and could not be downloaded. Audio conversion will fail.")

    app = YoutubeAudioConverter()
    app.mainloop()
    return 0
