from __future__ import annotations

import contextlib
import itertools
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

from yt_dlp.postprocessor import ffmpeg as yt_ffmpeg


ProgressCallback = Callable[["FFmpegProgress"], None]


@dataclass
class FFmpegProgress:
    raw: str
    time_seconds: float = 0.0
    time_text: str = ""
    speed: str = ""
    size: str = ""
    bitrate: str = ""
    completed: bool = False


_state = threading.local()
_install_lock = threading.Lock()
_installed = False
_original_real_run = yt_ffmpeg.FFmpegPostProcessor.real_run_ffmpeg
_FIELD_RE = re.compile(r"(?P<key>frame|fps|q|size|time|bitrate|speed)\s*=\s*(?P<value>[^\s\r\n]+)")
_STALL_TIMEOUT_SECONDS = 300.0
_GATED_POSTPROCESSORS = {
    "FFmpegConcatPP",
    "FFmpegCopyStreamPP",
    "FFmpegExtractAudioPP",
    "FFmpegMergerPP",
    "FFmpegVideoConvertorPP",
    "FFmpegVideoRemuxerPP",
}


def install_ffmpeg_progress_patch() -> None:
    global _installed
    with _install_lock:
        if _installed:
            return
        yt_ffmpeg.FFmpegPostProcessor.real_run_ffmpeg = _patched_real_run_ffmpeg
        _installed = True


@contextlib.contextmanager
def ffmpeg_progress_context(callback: ProgressCallback | None, conversion_gate=None):
    install_ffmpeg_progress_patch()
    previous_callback = getattr(_state, "callback", None)
    previous_gate = getattr(_state, "conversion_gate", None)
    _state.callback = callback
    _state.conversion_gate = conversion_gate
    try:
        yield
    finally:
        _state.callback = previous_callback
        _state.conversion_gate = previous_gate


def parse_ffmpeg_status(text: str) -> FFmpegProgress | None:
    if "time=" not in text and "size=" not in text:
        return None

    fields = {match.group("key"): match.group("value") for match in _FIELD_RE.finditer(text)}
    if not fields:
        return None

    time_text = fields.get("time", "")
    return FFmpegProgress(
        raw=text.strip(),
        time_seconds=_parse_time(time_text),
        time_text=time_text,
        speed=fields.get("speed", ""),
        size=fields.get("size", ""),
        bitrate=fields.get("bitrate", ""),
    )


def _parse_time(value: str) -> float:
    if not value or value == "N/A":
        return 0.0
    try:
        hours, minutes, seconds = value.split(":", 2)
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError):
        return 0.0


def _patched_real_run_ffmpeg(self, input_path_opts, output_path_opts, *, expected_retcodes=(0,)):
    callback = getattr(_state, "callback", None)
    conversion_gate = getattr(_state, "conversion_gate", None)
    if callback is None:
        return _original_real_run(self, input_path_opts, output_path_opts, expected_retcodes=expected_retcodes)

    if not _uses_conversion_gate(self):
        return _run_ffmpeg_with_progress(self, input_path_opts, output_path_opts, expected_retcodes, None)

    if conversion_gate is None:
        return _run_ffmpeg_with_progress(self, input_path_opts, output_path_opts, expected_retcodes, callback)

    conversion_gate.acquire()
    try:
        return _run_ffmpeg_with_progress(self, input_path_opts, output_path_opts, expected_retcodes, callback)
    finally:
        conversion_gate.release()


def _uses_conversion_gate(postprocessor) -> bool:
    return type(postprocessor).__name__ in _GATED_POSTPROCESSORS


def _run_ffmpeg_with_progress(self, input_path_opts, output_path_opts, expected_retcodes, callback):

    self.check_version()
    oldest_mtime = min(os.stat(path).st_mtime for path, _ in input_path_opts if path)

    cmd = [self.executable, yt_ffmpeg.encodeArgument("-y")]
    if self.basename == "ffmpeg":
        cmd += [
            yt_ffmpeg.encodeArgument("-hide_banner"),
            yt_ffmpeg.encodeArgument("-nostdin"),
            yt_ffmpeg.encodeArgument("-loglevel"),
            yt_ffmpeg.encodeArgument("repeat+info"),
        ]

    def make_args(file, args, name, number):
        keys = [f"_{name}{number}", f"_{name}"]
        if name == "o" and _should_faststart(file):
            args += ["-movflags", "+faststart"]
            if number == 1:
                keys.append("")
        args += self._configuration_args(self.basename, keys)
        if name == "i":
            args.append("-i")
        return [yt_ffmpeg.encodeArgument(arg) for arg in args] + [self._ffmpeg_filename_argument(file)]

    for arg_type, path_opts in (("i", input_path_opts), ("o", output_path_opts)):
        cmd += itertools.chain.from_iterable(
            make_args(path, list(opts), arg_type, index + 1)
            for index, (path, opts) in enumerate(path_opts)
            if path
        )

    self.write_debug(f"ffmpeg command line: {yt_ffmpeg.shell_quote(cmd)}")

    popen_kwargs = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(cmd, **popen_kwargs)
    if proc.stdin:
        proc.stdin.close()

    assert proc.stderr is not None
    stderr_queue: queue.Queue[bytes | None] = queue.Queue()
    reader = threading.Thread(target=_read_stderr, args=(proc.stderr, stderr_queue), daemon=True)
    reader.start()

    stderr_chunks: list[bytes] = []
    partial = ""
    decoder = _IncrementalDecoder()
    last_progress: FFmpegProgress | None = None
    last_output_time = time.monotonic()
    stalled = False
    stall_reason = ""

    def capture_progress(progress: FFmpegProgress) -> None:
        nonlocal last_progress
        last_progress = progress
        if callback:
            callback(progress)

    while True:
        try:
            chunk = stderr_queue.get(timeout=1.0)
        except queue.Empty:
            if proc.poll() is not None and not reader.is_alive():
                break
            if time.monotonic() - last_output_time > _STALL_TIMEOUT_SECONDS:
                stalled = True
                stall_reason = f"no stderr output for {_STALL_TIMEOUT_SECONDS:g}s"
                proc.kill()
                break
            continue

        if chunk is None:
            break
        last_output_time = time.monotonic()
        stderr_chunks.append(chunk)
        partial = _consume_progress_text(partial + decoder.decode(chunk), capture_progress)

    reader.join(timeout=2.0)
    tail = decoder.decode(b"", final=True)
    if tail:
        partial = _consume_progress_text(partial + tail, capture_progress)
    if partial:
        _emit_progress(partial, capture_progress)

    returncode = proc.wait()
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")

    if stalled:
        self.write_debug(stderr)
        raise yt_ffmpeg.FFmpegPostProcessorError(f"ffmpeg stalled: {stall_reason}")

    if returncode not in yt_ffmpeg.variadic(expected_retcodes):
        self.write_debug(stderr)
        last_line = stderr.strip().splitlines()[-1] if stderr.strip() else f"ffmpeg exited with {returncode}"
        raise yt_ffmpeg.FFmpegPostProcessorError(last_line)

    for out_path, _ in output_path_opts:
        if out_path:
            self.try_utime(out_path, oldest_mtime, oldest_mtime)
    if callback and last_progress:
        callback(
            FFmpegProgress(
                raw="ffmpeg complete",
                time_seconds=last_progress.time_seconds,
                time_text=last_progress.time_text,
                speed=last_progress.speed,
                size=last_progress.size,
                bitrate=last_progress.bitrate,
                completed=True,
            )
        )
    return stderr


def _should_faststart(output_path: str) -> bool:
    ext = os.path.splitext(str(output_path or ""))[1].lower()
    return ext in {".mp4", ".mov"}


def _read_stderr(stream, stderr_queue: queue.Queue[bytes | None]) -> None:
    try:
        while True:
            chunk = os.read(stream.fileno(), 4096)
            if not chunk:
                break
            stderr_queue.put(chunk)
    finally:
        stderr_queue.put(None)


class _IncrementalDecoder:
    def __init__(self):
        import codecs

        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def decode(self, value: bytes, final: bool = False) -> str:
        return self._decoder.decode(value, final=final)


def _consume_progress_text(text: str, callback: ProgressCallback) -> str:
    start = 0
    for index, char in enumerate(text):
        if char in "\r\n":
            segment = text[start:index]
            if segment:
                _emit_progress(segment, callback)
            start = index + 1
    return text[start:]


def _emit_progress(segment: str, callback: ProgressCallback) -> None:
    progress = parse_ffmpeg_status(segment)
    if progress:
        callback(progress)
