"""Dark / light QSS themes with readable contrast (features 152, 155, 156)."""

from __future__ import annotations

DARK = """
QWidget { background: #0f1419; color: #e6edf3; font-size: 14px; font-family: "Segoe UI", "Ubuntu", sans-serif; }
QMainWindow, QDialog { background: #0f1419; }
QLabel#title { font-size: 22px; font-weight: 600; color: #79c0ff; }
QLabel#subtitle { color: #8b949e; }
QLabel#danger { color: #ffa198; }
QLabel#warn { color: #e3b341; }
QFrame#card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; }
QWidget:focus { outline: 2px solid #79c0ff; }
QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background: #30363d; }
QPushButton#primary { background: #1f6feb; border: 1px solid #388bfd; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #388bfd; }
QPushButton#danger { background: #8b2121; border: 1px solid #f85149; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {
  background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 6px;
  selection-background-color: #1f6feb;
}
QTableWidget { background: #0d1117; gridline-color: #30363d; alternate-background-color: #161b22; }
QHeaderView::section { background: #161b22; color: #8b949e; padding: 6px; border: 0; }
QProgressBar { border: 1px solid #30363d; border-radius: 6px; background: #0d1117; text-align: center; }
QProgressBar::chunk { background: #1f6feb; border-radius: 6px; }
QListWidget { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; }
QListWidget::item { padding: 10px; }
QListWidget::item:selected { background: #1f6feb; }
QCheckBox, QRadioButton { spacing: 8px; }
QScrollBar:vertical { background: #0d1117; width: 10px; }
QScrollBar::handle:vertical { background: #30363d; border-radius: 4px; }
QSplitter::handle { background: #30363d; }
QStatusBar { background: #161b22; color: #8b949e; }
"""

LIGHT = """
QWidget { background: #f6f8fa; color: #1f2328; font-size: 14px; font-family: "Segoe UI", "Ubuntu", sans-serif; }
QMainWindow, QDialog { background: #f6f8fa; }
QLabel#title { font-size: 22px; font-weight: 600; color: #0969da; }
QLabel#subtitle { color: #656d76; }
QLabel#danger { color: #a40e26; }
QLabel#warn { color: #9a6700; }
QFrame#card { background: white; border: 1px solid #d0d7de; border-radius: 10px; }
QPushButton { background: white; border: 1px solid #d0d7de; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background: #eaeef2; }
QPushButton#primary { background: #0969da; border: 1px solid #0969da; color: white; font-weight: 600; }
QPushButton#danger { background: #cf222e; color: white; border: 1px solid #cf222e; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {
  background: white; border: 1px solid #d0d7de; border-radius: 6px; padding: 6px;
}
QTableWidget { background: white; gridline-color: #d0d7de; alternate-background-color: #f6f8fa; }
QHeaderView::section { background: #f6f8fa; color: #656d76; padding: 6px; border: 0; }
QProgressBar { border: 1px solid #d0d7de; border-radius: 6px; background: white; text-align: center; }
QProgressBar::chunk { background: #0969da; border-radius: 6px; }
QListWidget { background: white; border: 1px solid #d0d7de; border-radius: 8px; }
QListWidget::item { padding: 10px; }
QListWidget::item:selected { background: #0969da; color: white; }
QStatusBar { background: white; color: #656d76; }
"""


def stylesheet(theme: str) -> str:
    return LIGHT if theme == "light" else DARK
