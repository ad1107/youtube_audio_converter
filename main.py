import sys

from cli_runner import build_parser, run_cli
from gui import YoutubeAudioConverter
from ffmpeg_dl import download_ffmpeg_if_needed

def _should_use_cli(args) -> bool:
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

    if _should_use_cli(args):
        return run_cli(args)

    if not download_ffmpeg_if_needed():
        print('WARNING: ffmpeg not found in PATH and could not be downloaded. Audio conversion will fail.')

    app = YoutubeAudioConverter()
    app.mainloop()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
