import queue
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

from .models import LOG_COLOURS


class GUILogMixin:
    def _poll_log_queue(self):
        try:
            while True:
                self._write_log(*self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(40, self._poll_log_queue)

    def _write_log(self, source: str, message: str, level: str, ts: datetime):
        self.log_text.config(state="normal")
        level_tag = level if level in LOG_COLOURS else "INFO"
        self.log_text.insert("end", f"[{ts.strftime('%H:%M:%S')}] ", "TS")
        self.log_text.insert("end", f"[{level:<8s}] ", level_tag)
        if source and source.upper() != "SYSTEM":
            self.log_text.insert("end", f"[{source[:38]:<38s}] ", "SRC")
        self.log_text.insert("end", f"{message}\n", level_tag)
        if hasattr(self, "var_autoscroll") and self.var_autoscroll.get():
            self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All", "*.*")],
            initialfile=f"audiobook_log_{datetime.now():%Y%m%d_%H%M%S}.txt",
        )
        if path:
            Path(path).write_text(self.log_text.get("1.0", "end"), encoding="utf-8")
            self.log("SYSTEM", f"Log saved -> {path}", "SUCCESS")
