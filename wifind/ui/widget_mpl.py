"""Widget matplotlib embebido en PyQt6."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget


class LienzoMpl(FigureCanvasQTAgg):
    def __init__(self, figure: Figure | None = None, parent: QWidget | None = None) -> None:
        self.figure = figure or Figure(figsize=(5, 4), dpi=100)
        super().__init__(self.figure)
        self.setParent(parent)


class PanelMpl(QWidget):
    """Panel con canvas matplotlib y barra de navegación opcional."""

    def __init__(
        self,
        figure: Figure | None = None,
        show_toolbar: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.canvas = LienzoMpl(figure, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        if show_toolbar:
            layout.addWidget(NavigationToolbar2QT(self.canvas, self))

    def set_figure(self, figure: Figure) -> None:
        from matplotlib import pyplot as plt

        old = self.canvas.figure
        if old is not figure:
            figure.set_canvas(self.canvas)
            self.canvas.figure = figure
            if old is not None:
                plt.close(old)
        self.canvas.draw_idle()

    def clear(self) -> None:
        self.canvas.figure.clear()
        self.canvas.draw()
