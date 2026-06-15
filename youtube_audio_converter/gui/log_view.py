import html
from datetime import datetime
from pathlib import Path

from PySide6 import QtGui, QtWidgets

from .models import LOG_COLOURS, Theme


class LogViewMixin:
    def _write_log_batch(self, entries):
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        for source, message, level, ts in entries:
            color = LOG_COLOURS.get(level, LOG_COLOURS["INFO"])
            ts_text = html.escape(ts.strftime("%H:%M:%S"))
            level_text = html.escape(f"{level:<8s}")
            source_text = ""
            if source and source.upper() != "SYSTEM":
                source_text = f' <span style="color:{Theme.PURPLE}">[{html.escape(source[:38]):<38s}]</span>'
            message_text = html.escape(str(message))
            line = (
                f'<span style="color:{Theme.MUTED}">[{ts_text}]</span> '
                f'<span style="color:{color}">[{level_text}]</span>'
                f"{source_text} "
                f'<span style="color:{color}">{message_text}</span><br>'
            )
            cursor.insertHtml(line)
        if self.autoscroll_check.isChecked():
            self.log_text.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def _clear_logs(self):
        self.log_text.clear()

    def _save_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Log",
            f"audiobook_log_{datetime.now():%Y%m%d_%H%M%S}.txt",
            "Text files (*.txt);;All Files (*.*)",
        )
        if path:
            Path(path).write_text(self.log_text.toPlainText(), encoding="utf-8")
            self.log("SYSTEM", f"Log saved -> {path}", "SUCCESS")
