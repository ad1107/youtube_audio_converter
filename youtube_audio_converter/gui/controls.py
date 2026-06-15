import os
import subprocess
import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets
from yt_dlp.version import __version__ as YTDLP_VERSION

from youtube_audio_converter import dependencies
from youtube_audio_converter.core.formats import quality_labels_for_format, supports_audio_filters
from youtube_audio_converter.core.urls import parse_source_line

from .models import FORMATS, Theme


class ControlsMixin:
    def _add_playlist_row(self, url_text: str = ""):
        row = self.url_table.rowCount()
        self.url_table.insertRow(row)
        item = QtWidgets.QTableWidgetItem(url_text)
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        self.url_table.setItem(row, 0, item)
        self.url_table.setCurrentCell(row, 0)

    def _remove_selected_url_rows(self):
        rows = sorted({index.row() for index in self.url_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.url_table.removeRow(row)
        if self.url_table.rowCount() == 0:
            self._add_playlist_row()

    def _clear_playlist_rows(self):
        self.url_table.setRowCount(0)
        self._add_playlist_row()
        self._add_playlist_row()

    def _import_txt(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Source TXT File",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not filename:
            return
        try:
            text = Path(filename).read_text(encoding="utf-8-sig")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Read Error", f"Failed to read file: {exc}")
            return
        self._add_lines_to_rows(text)

    def _paste_urls(self):
        text = QtWidgets.QApplication.clipboard().text()
        self._add_lines_to_rows(text)

    def _add_lines_to_rows(self, text: str):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return

        empty_rows = []
        for row in range(self.url_table.rowCount()):
            item = self.url_table.item(row, 0)
            if item is None or not item.text().strip():
                empty_rows.append(row)

        for index, line in enumerate(lines):
            if index < len(empty_rows):
                row = empty_rows[index]
                item = self.url_table.item(row, 0) or QtWidgets.QTableWidgetItem()
                item.setText(line)
                self.url_table.setItem(row, 0, item)
            else:
                self._add_playlist_row(line)

    def _url_sources(self) -> list[tuple[str | None, str]]:
        sources = []
        for row in range(self.url_table.rowCount()):
            item = self.url_table.item(row, 0)
            text = item.text().strip() if item else ""
            if text:
                sources.append(parse_source_line(text) or (None, text))
        return sources

    def _browse_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_dir_edit.text())
        if path:
            self.output_dir_edit.setText(path)

    def _browse_cookies(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select YouTube cookies file",
            "",
            "Cookies / Text files (*.txt);;All Files (*.*)",
        )
        if path:
            self.cookiefile_edit.setText(path)

    def _clear_cookies(self):
        self.cookiefile_edit.clear()
        self.browser_combo.setCurrentText("None")

    def _open_output_dir(self):
        path = self.output_dir_edit.text().strip()
        os.makedirs(path, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.run(["xdg-open", path], check=False)

    def _on_format_changed(self):
        fmt_code = FORMATS.get(self.format_combo.currentText(), "m4a") if hasattr(self, "format_combo") else "m4a"
        quality_labels = quality_labels_for_format(fmt_code)
        current = self.quality_combo.currentText() if hasattr(self, "quality_combo") else ""
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        self.quality_combo.addItems(quality_labels)
        if current in quality_labels:
            self.quality_combo.setCurrentText(current)
        self.quality_combo.setEnabled(len(quality_labels) > 1)
        self.quality_combo.blockSignals(False)

        audio_enabled = supports_audio_filters(fmt_code)
        self.speed_combo.setEnabled(audio_enabled)
        self.volume_spin.setEnabled(audio_enabled)

    def _download_deno(self):
        if dependencies.download_deno_if_needed(self):
            self.use_deno_check.setEnabled(True)
            self._check_dependencies()

    def _check_dependencies(self):
        has_ffmpeg = bool(dependencies.get_ffmpeg_path())
        has_deno = bool(dependencies.get_deno_path())
        status_text = f"yt-dlp {YTDLP_VERSION}"
        if has_ffmpeg:
            status_text += "  ffmpeg"
        if has_deno:
            status_text += "  deno"

        if has_ffmpeg:
            self.lbl_dep_status.setText(status_text)
            self.lbl_dep_status.setStyleSheet(f"color: {Theme.GREEN};")
            if not self.is_running:
                self.btn_start.setEnabled(True)
        else:
            self.lbl_dep_status.setText("Missing: ffmpeg")
            self.lbl_dep_status.setStyleSheet(f"color: {Theme.YELLOW};")
            self.btn_start.setEnabled(False)

        self.use_deno_check.setEnabled(has_deno)
        if not has_deno:
            self.use_deno_check.setChecked(False)
