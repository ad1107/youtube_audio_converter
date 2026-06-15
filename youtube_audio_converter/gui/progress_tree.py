from PySide6 import QtCore, QtGui, QtWidgets

from .models import Theme
from .signals import ACTIVE_ROLE, PHASE_ROLE, PROGRESS_ROLE, TONE_ROLE


class ProgressBarDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index.column() != 3:
            super().paint(painter, option, index)
            return

        value = index.data(PROGRESS_ROLE)
        if value is None:
            super().paint(painter, option, index)
            return

        try:
            value = max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            value = 0.0

        painter.save()
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QtGui.QColor(Theme.BG4))

        rect = option.rect.adjusted(12, 8, -12, -8)
        if rect.height() > 10:
            center = rect.center()
            rect.setHeight(8)
            rect.moveCenter(center)

        phase = index.data(PHASE_ROLE) or "download"
        tone = index.data(TONE_ROLE) or phase
        colors = {
            "download": Theme.ACCENT,
            "convert": Theme.PURPLE,
            "done": Theme.GREEN,
            "skipped": Theme.GREEN,
            "failed": Theme.RED,
            "error": Theme.RED,
            "success": Theme.GREEN,
        }
        fill_color = QtGui.QColor(colors.get(tone, colors.get(phase, Theme.ACCENT)))
        bg_color = QtGui.QColor(Theme.BG3)

        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, 4, 4)
        fill_rect = QtCore.QRect(rect)
        fill_rect.setWidth(max(1, int(rect.width() * value / 100.0)))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(fill_rect, 4, 4)

        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""
        painter.setPen(QtGui.QColor(Theme.TEXT))
        painter.drawText(option.rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class ProgressTree(QtWidgets.QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.job_items: dict[int, QtWidgets.QTreeWidgetItem] = {}
        self.item_items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self.item_states: dict[str, dict] = {}
        self.hide_inactive = True

        self.setColumnCount(5)
        self.setHeaderLabels(["Task", "Phase", "Status", "Progress", "Detail"])
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(False)
        self.setUniformRowHeights(True)
        self.setIndentation(18)
        self.setItemDelegateForColumn(3, ProgressBarDelegate(self))
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setWordWrap(False)

        header = self.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.resizeSection(3, 140)

    def reset(self):
        self.clear()
        self.job_items.clear()
        self.item_items.clear()
        self.item_states.clear()

    def set_hide_inactive(self, value: bool):
        self.hide_inactive = bool(value)
        for key, item in self.item_items.items():
            state = self.item_states.get(key, {})
            item.setHidden(self._should_hide_item(state))

    def apply_job_state(self, job_id: int, state: dict):
        item = self.job_items.get(job_id)
        if item is None:
            item = QtWidgets.QTreeWidgetItem(self)
            self.job_items[job_id] = item
            item.setExpanded(True)
            font = item.font(0)
            font.setBold(True)
            for column in range(self.columnCount()):
                item.setFont(column, font)

        title = state.get("title") or f"#{job_id + 1} Fetching..."
        status = state.get("status") or "Fetching"
        percent = state.get("percent", 0)
        detail = state.get("detail") or ""
        phase = state.get("phase") or "download"
        tone = state.get("tone") or phase

        item.setText(0, title)
        item.setText(1, "Job")
        item.setText(2, status)
        item.setText(3, f"{int(max(0, min(100, percent)))}%")
        item.setText(4, detail)
        item.setData(3, PROGRESS_ROLE, percent)
        item.setData(3, PHASE_ROLE, phase)
        item.setData(3, TONE_ROLE, tone)
        item.setForeground(0, QtGui.QBrush(QtGui.QColor(self._tone_color(tone))))

    def apply_item_state(self, key: str, state: dict):
        self.item_states[key] = dict(state)
        job_id = int(state.get("job_id", 0))
        parent = self.job_items.get(job_id)
        if parent is None:
            self.apply_job_state(
                job_id,
                {
                    "title": f"#{job_id + 1} {state.get('job_title') or 'Fetching...'}",
                    "status": "Fetching",
                    "percent": 0,
                },
            )
            parent = self.job_items[job_id]

        item = self.item_items.get(key)
        if item is None:
            item = QtWidgets.QTreeWidgetItem(parent)
            self.item_items[key] = item

        percent = state.get("percent")
        progress_text = "" if percent is None else f"{int(max(0, min(100, float(percent))))}%"
        tone = state.get("tone") or state.get("phase") or "download"
        item.setText(0, f"{int(state.get('item_index', 0)):02d}. {state.get('item_title') or 'Untitled'}")
        item.setText(1, self._phase_label(state.get("phase") or "download"))
        item.setText(2, state.get("status") or "")
        item.setText(3, progress_text)
        item.setText(4, state.get("detail") or "")
        item.setData(3, PROGRESS_ROLE, 0 if percent is None else percent)
        item.setData(3, PHASE_ROLE, state.get("phase") or "download")
        item.setData(3, ACTIVE_ROLE, bool(state.get("active", True)))
        item.setData(3, TONE_ROLE, tone)
        item.setForeground(0, QtGui.QBrush(QtGui.QColor(self._tone_color(tone))))
        item.setHidden(self._should_hide_item(state))
        parent.setExpanded(True)

    def _should_hide_item(self, state: dict) -> bool:
        return bool(self.hide_inactive and not state.get("active", True))

    @staticmethod
    def _phase_label(phase: str) -> str:
        return {
            "download": "Download",
            "convert": "Convert",
            "done": "Done",
            "skipped": "Skipped",
            "failed": "Failed",
        }.get(phase, phase.title())

    @staticmethod
    def _tone_color(tone: str) -> str:
        return {
            "done": Theme.GREEN,
            "success": Theme.GREEN,
            "skipped": Theme.MUTED,
            "failed": Theme.RED,
            "error": Theme.RED,
            "convert": Theme.PURPLE,
            "download": Theme.TEXT,
        }.get(tone, Theme.TEXT)
