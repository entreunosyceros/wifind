"""Gráfico de histórico de escaneos (actualización in-place)."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from wifind.ui.mpl_estilo import aplicar_tema_ejes, aplicar_tema_leyenda, colores_tema


class GraficoHistorico(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = "dark"

        self._fig = Figure(figsize=(6, 3.5), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._ax2 = self._ax.twinx()
        self._canvas = FigureCanvasQTAgg(self._fig)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._line_counts = None
        self._line_avg = None
        self._legend = None
        self._empty_text = None

        self._fig.subplots_adjust(left=0.10, right=0.88, top=0.88, bottom=0.18)
        self._aplicar_estilo_base()

    def _aplicar_estilo_base(self) -> None:
        c = colores_tema(self._theme)
        self._ax.set_title("Histórico de escaneos")
        self._ax.set_xlabel("Tiempo (s)")
        self._ax.set_ylabel("Redes visibles")
        self._ax2.set_ylabel("Señal media (dBm)")
        aplicar_tema_ejes(self._fig, self._ax, self._theme)
        self._ax2.tick_params(colors=c["text"])
        self._ax2.yaxis.label.set_color(c["text"])
        for spine in self._ax2.spines.values():
            spine.set_color(c["spine"])

        if self._empty_text is None:
            self._empty_text = self._ax.text(
                0.5,
                0.5,
                "Sin histórico de escaneos",
                transform=self._ax.transAxes,
                ha="center",
                va="center",
                color=c["text_muted"],
                zorder=0,
            )

    def actualizar(self, snapshots, theme: str = "dark") -> None:
        if theme != self._theme:
            self._theme = theme
            self._line_counts = None
            self._line_avg = None
            if self._legend is not None:
                self._legend.remove()
                self._legend = None
            if self._empty_text is not None:
                self._empty_text.remove()
                self._empty_text = None
            self._aplicar_estilo_base()

        hay_datos = bool(snapshots)
        if self._empty_text is not None:
            self._empty_text.set_visible(not hay_datos)

        if not hay_datos:
            self._ocultar_series()
            self._canvas.draw_idle()
            return

        times = [s.timestamp - snapshots[0].timestamp for s in snapshots]
        counts = [s.numero_redes for s in snapshots]
        avgs = [s.senal_media_dbm or 0 for s in snapshots]

        if self._line_counts is None:
            (self._line_counts,) = self._ax.plot(
                times, counts, label="Nº redes", color="#1976D2", linewidth=1.8, zorder=3,
            )
            (self._line_avg,) = self._ax2.plot(
                times, avgs, label="Señal media (dBm)", color="#FF9800", linewidth=1.8, zorder=2,
            )
            self._actualizar_leyenda()
        else:
            self._line_counts.set_data(times, counts)
            self._line_avg.set_data(times, avgs)
            self._line_counts.set_visible(True)
            self._line_avg.set_visible(True)

        if times:
            xmin, xmax = min(times), max(times)
            if xmin == xmax:
                self._ax.set_xlim(xmin - 1, xmax + 1)
            else:
                margin = max(0.5, (xmax - xmin) * 0.05)
                self._ax.set_xlim(xmin, xmax + margin)

        self._canvas.draw_idle()

    def _actualizar_leyenda(self) -> None:
        if self._legend is not None:
            self._legend.remove()
        lines = [self._line_counts, self._line_avg]
        labels = [line.get_label() for line in lines if line is not None]
        lines = [line for line in lines if line is not None]
        self._legend = self._ax.legend(lines, labels, loc="upper left", fontsize=8, framealpha=0.92)
        aplicar_tema_leyenda(self._legend, self._theme)

    def _ocultar_series(self) -> None:
        if self._line_counts is not None:
            self._line_counts.set_visible(False)
        if self._line_avg is not None:
            self._line_avg.set_visible(False)
