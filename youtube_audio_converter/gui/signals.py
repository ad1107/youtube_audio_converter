from PySide6 import QtCore


PROGRESS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
PHASE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2
ACTIVE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 3
TONE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 4


class GuiSignals(QtCore.QObject):
    log_entry = QtCore.Signal(str, str, str, object)
    current_text = QtCore.Signal(str)
    overall_state = QtCore.Signal(float, str)
    job_state = QtCore.Signal(int, object)
    item_state = QtCore.Signal(str, object)
    all_finished = QtCore.Signal()
