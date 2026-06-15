from PySide6 import QtGui

from .models import Theme


def app_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(Theme.BG))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(Theme.TEXT))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(Theme.BG2))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(Theme.BG3))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(Theme.BG3))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(Theme.TEXT))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(Theme.TEXT))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(Theme.BG3))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(Theme.TEXT))
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(Theme.WHITE))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(Theme.ACCENT))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(Theme.WHITE))
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(Theme.MUTED))
    return palette


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        background: {Theme.BG};
        color: {Theme.TEXT};
        font-family: "Segoe UI", "Microsoft Sans Serif", Arial, sans-serif;
        font-size: 10.5pt;
    }}
    QLabel {{
        background: transparent;
    }}
    QLabel#appTitle {{
        color: {Theme.WHITE};
        font-size: 15pt;
        font-weight: 600;
    }}
    QLabel#sectionLabel {{
        color: {Theme.ACCENT};
        font-size: 10pt;
        font-weight: 600;
    }}
    QLabel#muted,
    QLabel#mutedMono {{
        color: {Theme.MUTED};
    }}
    QLabel#mutedMono {{
        font-size: 9pt;
    }}
    QLabel#badgeReady,
    QLabel#badgeRunning {{
        border: 1px solid {Theme.BORDER};
        border-radius: 5px;
        font-size: 9pt;
        font-weight: 600;
        padding: 4px 9px;
    }}
    QLabel#badgeReady {{
        color: {Theme.GREEN};
        background: {Theme.BG3};
    }}
    QLabel#badgeRunning {{
        color: {Theme.YELLOW};
        background: {Theme.BG3};
    }}
    QLabel#dialogHeading {{
        color: {Theme.WHITE};
        font-size: 12pt;
        font-weight: 600;
    }}
    QFrame#card {{
        background: {Theme.BG2};
        border: 1px solid {Theme.BORDER};
        border-radius: 6px;
    }}
    QFrame#bottomBar {{
        background: {Theme.BG};
    }}
    QPushButton {{
        background: {Theme.BG3};
        color: {Theme.TEXT};
        border: 1px solid {Theme.BORDER};
        border-radius: 4px;
        min-height: 26px;
        padding: 3px 10px;
    }}
    QPushButton:hover {{
        background: {Theme.BG4};
        color: {Theme.WHITE};
        border-color: #5a5a5a;
    }}
    QPushButton:pressed {{
        background: #464646;
    }}
    QPushButton:disabled {{
        color: {Theme.MUTED};
        background: {Theme.BG2};
        border-color: #363636;
    }}
    QPushButton#primaryButton {{
        background: {Theme.ACCENT};
        color: {Theme.WHITE};
        font-weight: 600;
        min-height: 32px;
        padding: 4px 12px;
        border-color: {Theme.ACCENT};
    }}
    QPushButton#primaryButton:hover {{
        background: #1686d9;
        border-color: #1686d9;
    }}
    QPushButton#primaryButton:pressed {{
        background: #006cbe;
        border-color: #006cbe;
    }}
    QPushButton#dangerButton {{
        background: {Theme.RED};
        color: {Theme.WHITE};
        font-weight: 600;
        min-height: 32px;
        padding: 4px 12px;
        border-color: {Theme.RED};
    }}
    QPushButton#dangerButton:hover {{
        background: #e15f24;
        border-color: #e15f24;
    }}
    QPushButton#dangerButton:pressed {{
        background: #b83300;
        border-color: #b83300;
    }}
    QPushButton#primaryButton:disabled,
    QPushButton#dangerButton:disabled {{
        background: #2a2a2a;
        color: {Theme.MUTED};
        border-color: #3a3a3a;
    }}
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPlainTextEdit,
    QTextEdit {{
        background: {Theme.BG3};
        color: {Theme.TEXT};
        border: 1px solid {Theme.BORDER};
        border-radius: 4px;
        min-height: 24px;
        padding: 3px 7px;
        selection-background-color: {Theme.BG4};
    }}
    QLineEdit:focus,
    QComboBox:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus {{
        border-color: {Theme.ACCENT};
    }}
    QComboBox::drop-down {{
        border: 0;
        width: 24px;
    }}
    QTextEdit {{
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 9pt;
    }}
    QTableWidget,
    QTreeWidget {{
        background: {Theme.BG2};
        alternate-background-color: {Theme.BG3};
        color: {Theme.TEXT};
        border: 1px solid {Theme.BORDER};
        border-radius: 4px;
        gridline-color: {Theme.BORDER};
        selection-background-color: {Theme.BG4};
        selection-color: {Theme.WHITE};
    }}
    QTableWidget::item,
    QTreeWidget::item {{
        min-height: 25px;
        padding: 2px 6px;
    }}
    QHeaderView::section {{
        background: {Theme.BG3};
        color: {Theme.MUTED};
        border: 0;
        border-bottom: 1px solid {Theme.BORDER};
        padding: 5px 6px;
        font-size: 9pt;
        font-weight: 600;
    }}
    QProgressBar {{
        background: {Theme.BG3};
        border: 1px solid {Theme.BORDER};
        border-radius: 4px;
        min-height: 12px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {Theme.ACCENT};
        border-radius: 3px;
    }}
    QCheckBox {{
        spacing: 8px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
    }}
    QCheckBox::indicator:unchecked {{
        background: {Theme.BG3};
        border: 1px solid {Theme.BORDER};
        border-radius: 3px;
    }}
    QCheckBox::indicator:checked {{
        background: {Theme.ACCENT};
        border: 1px solid {Theme.ACCENT};
        border-radius: 3px;
    }}
    QTabWidget::pane {{
        border: 1px solid {Theme.BORDER};
        border-radius: 4px;
        top: -1px;
    }}
    QTabBar::tab {{
        background: {Theme.BG3};
        color: {Theme.TEXT};
        border: 1px solid {Theme.BORDER};
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        min-height: 28px;
        padding: 5px 15px;
    }}
    QTabBar::tab:selected {{
        background: {Theme.ACCENT};
        color: {Theme.WHITE};
        font-weight: 600;
    }}
    QTabBar::tab:!selected:hover {{
        background: {Theme.BG4};
    }}
    QScrollBar:vertical,
    QScrollBar:horizontal {{
        background: {Theme.BG2};
        border: 0;
        width: 10px;
        height: 10px;
    }}
    QScrollBar::handle:vertical,
    QScrollBar::handle:horizontal {{
        background: {Theme.BG4};
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover,
    QScrollBar::handle:horizontal:hover {{
        background: #555555;
    }}
    QSplitter::handle {{
        background: {Theme.BORDER};
    }}
    QSplitter::handle:horizontal {{
        width: 6px;
        margin: 0;
        border-radius: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 6px;
        margin: 0;
        border-radius: 2px;
    }}
    QSplitter::handle:hover {{
        background: {Theme.ACCENT};
    }}
    QScrollBar::add-line,
    QScrollBar::sub-line {{
        width: 0;
        height: 0;
    }}
    """
