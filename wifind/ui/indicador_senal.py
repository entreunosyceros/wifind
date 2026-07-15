"""Indicador visual de intensidad WiFi (rayas / barras)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

_COLORES_ACTIVAS = ("#F44336", "#FF9800", "#FFC107", "#4CAF50")
_COLOR_INACTIVA = "#B0BEC5"
_COLOR_INACTIVA_OSCURO = "#546E7A"

NUM_BARRAS = 4


class IndicadorSenal(QWidget):
    """Cuatro barras verticales: cuantas más, mejor la señal."""

    def __init__(
        self,
        barras: int = 0,
        *,
        theme: str = "dark",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._barras = max(0, min(NUM_BARRAS, barras))
        self._theme = theme
        self.setFixedSize(52, 20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip(self._tooltip())

    def establecer_barras(self, barras: int, *, signal_dbm: int | None = None) -> None:
        self._barras = max(0, min(NUM_BARRAS, barras))
        if signal_dbm is not None:
            self.setToolTip(f"Señal: {signal_dbm} dBm — {self._tooltip()}")
        else:
            self.setToolTip(self._tooltip())
        self.update()

    def establecer_tema(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def _tooltip(self) -> str:
        textos = {
            0: "Sin señal",
            1: "Señal muy débil",
            2: "Señal regular",
            3: "Buena señal",
            4: "Señal excelente",
        }
        return textos.get(self._barras, "")

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inactiva = QColor(_COLOR_INACTIVA_OSCURO if self._theme == "dark" else _COLOR_INACTIVA)
        activa = QColor(_COLORES_ACTIVAS[min(max(self._barras, 1), 4) - 1] if self._barras else inactiva)

        ancho = 8
        sep = 4
        alturas = (5, 9, 13, 17)
        base_y = self.height() - 2

        for i in range(NUM_BARRAS):
            x = 2 + i * (ancho + sep)
            h = alturas[i]
            y = base_y - h
            color = activa if i < self._barras else inactiva
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(x, y, ancho, h, 2, 2)

        painter.end()
