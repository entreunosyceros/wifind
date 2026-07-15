"""Temas claro/oscuro para WiFind."""

LIGHT_QSS = """
QMainWindow, QWidget { background: #f5f5f5; color: #212121; }
QTabWidget::pane { border: 1px solid #ccc; }
QHeaderView::section { background: #e0e0e0; padding: 4px; }
QTableWidget { gridline-color: #ddd; }
QGroupBox { font-weight: bold; border: 1px solid #bbb; margin-top: 8px; padding-top: 8px; }
QPushButton { padding: 6px 12px; background: #1976D2; color: white; border: none; border-radius: 4px; }
QPushButton:disabled { background: #aaa; }
QPushButton:hover:!disabled { background: #1565C0; }
QMenuBar { background: #eeeeee; }
QToolBar { background: #eeeeee; border-bottom: 1px solid #ccc; }
FigureCanvasQTAgg { background-color: transparent; }
"""

DARK_QSS = """
QMainWindow, QWidget { background: #2b2b2b; color: #e0e0e0; }
QTabWidget::pane { border: 1px solid #555; }
QHeaderView::section { background: #3c3c3c; color: #eee; padding: 4px; }
QTableWidget { gridline-color: #555; background: #333; color: #eee; }
QGroupBox { font-weight: bold; border: 1px solid #666; margin-top: 8px; padding-top: 8px; }
QPushButton { padding: 6px 12px; background: #1976D2; color: white; border: none; border-radius: 4px; }
QPushButton:disabled { background: #555; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #3c3c3c; color: #eee; border: 1px solid #666; padding: 3px; }
QMenuBar, QToolBar { background: #333; color: #eee; border-bottom: 1px solid #555; }
QMenu { background: #333; color: #eee; }
QStatusBar { background: #333; color: #eee; }
FigureCanvasQTAgg { background-color: transparent; }
"""


def aplicar_tema(app, theme: str) -> None:
    if theme == "dark":
        app.setStyleSheet(DARK_QSS)
    else:
        app.setStyleSheet(LIGHT_QSS)
