from ..dependencies import get_deno_path
from .cookies import normalize_cookiesfrombrowser
from .formats import final_output_ext, get_format_spec, ydl_format_selector
from .yt_logger import YTLogger


def build_ydl_options(
    settings,
    outtmpl: str | None,
    logger,
    noplaylist: bool,
    include_postprocessors: bool,
    ignoreerrors: bool,
    postprocessors=None,
    postprocessor_args=None,
    progress_hook=None,
    postprocessor_hook=None,
) -> dict:
    spec = get_format_spec(settings.fmt)
    opts = {
        "format": ydl_format_selector(settings.fmt, settings.quality),
        "noplaylist": noplaylist,
        "ignoreerrors": ignoreerrors,
        "no_warnings": False,
        "quiet": True,
        "color": "no_color",
        "overwrites": not settings.skip_existing,
        "nooverwrites": settings.skip_existing,
        "final_ext": final_output_ext(settings.fmt),
        "concurrent_fragment_downloads": 4,
        "logger": logger,
    }
    if spec.merge_output_format:
        opts["merge_output_format"] = spec.merge_output_format
    if outtmpl:
        opts["outtmpl"] = outtmpl
    if include_postprocessors:
        opts["postprocessors"] = postprocessors or []
        opts["postprocessor_args"] = postprocessor_args or {}
        opts["writethumbnail"] = settings.embed_thumbnail and spec.supports_thumbnail
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook:
        opts["postprocessor_hooks"] = [postprocessor_hook]

    if settings.use_deno:
        deno_path = get_deno_path()
        if deno_path:
            opts["js_runtimes"] = {"deno": {"path": deno_path}}
            opts["remote_components"] = ["ejs:github"]

    if settings.cookiefile:
        opts["cookiefile"] = settings.cookiefile
    elif settings.cookies_browser and settings.cookies_browser != "None":
        cookies = normalize_cookiesfrombrowser(settings.cookies_browser)
        if cookies:
            opts["cookiesfrombrowser"] = cookies

    if settings.track_num and settings.embed_metadata:
        opts["parse_metadata"] = ["%(playlist_index)s:%(track_number)s"]

    return opts


def build_yt_logger(job, settings, callbacks):
    def debug(message):
        if settings.verbose or "ffmpeg command line:" in message:
            callbacks.log(getattr(job, "playlist_title", "") or job.url[:60], message, "DEBUG")

    return YTLogger(
        cb_info=None,
        cb_warn=lambda message: callbacks.log(getattr(job, "playlist_title", "") or job.url[:60], message, "WARNING"),
        cb_err=lambda message: callbacks.log(getattr(job, "playlist_title", "") or job.url[:60], message, "ERROR"),
        cb_debug=debug,
        suppress_js_warnings=settings.suppress_js_warnings,
    )
