class YTLogger:
    """Routes yt-dlp logger calls to caller-provided callbacks."""

    def __init__(self, cb_info=None, cb_warn=None, cb_err=None, cb_debug=None, suppress_js_warnings=False):
        self._info = cb_info
        self._warn = cb_warn
        self._err = cb_err
        self._debug = cb_debug
        self._suppress_js_warnings = suppress_js_warnings

    def debug(self, msg):
        if msg.startswith("[debug]"):
            if self._debug:
                self._debug(msg)
        elif self._info:
            self._info(msg)

    def info(self, msg):
        if self._info:
            self._info(msg)

    def warning(self, msg):
        if self._suppress_js_warnings and _is_js_warning(msg):
            return
        if self._warn:
            self._warn(msg)

    def error(self, msg):
        if self._err:
            self._err(msg)


def _is_js_warning(msg: str) -> bool:
    value = msg.lower()
    return any(
        marker in value
        for marker in ["javascript runtime", "[jsc]", "n challenge", "deno process"]
    )
