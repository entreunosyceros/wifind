"""Gráfico de intensidad en vivo (actualización in-place, sin parpadeos)."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from wifind.ui.mpl_estilo import aplicar_tema_ejes, aplicar_tema_leyenda, colores_tema


class GraficoIntensidadEnVivo(QWidget):
    """Mantiene una sola figura matplotlib y solo actualiza los datos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = "dark"
        self._thresholds = {"good": -50, "fair": -70}
        self._ssid = ""

        self._fig = Figure(figsize=(6, 3.5), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._line = None
        self._fill = None
        self._hline_fair = None
        self._hline_good = None
        self._legend = None
        self._empty_text = None

        self._fig.subplots_adjust(left=0.10, right=0.97, top=0.88, bottom=0.18)
        self._aplicar_estilo_base()

    def _aplicar_estilo_base(self) -> None:
        c = colores_tema(self._theme)
        self._ax.set_ylim(-100, -30)
        self._ax.set_xlabel("Tiempo (s)")
        self._ax.set_ylabel("Señal (dBm)")
        aplicar_tema_ejes(self._fig, self._ax, self._theme)

        if self._hline_fair is None:
            self._hline_fair = self._ax.axhline(
                self._thresholds["fair"],
                color="#FF9800",
                linestyle="--",
                linewidth=1,
                label=f"Umbral débil ({self._thresholds['fair']} dBm)",
                zorder=1,
            )
            self._hline_good = self._ax.axhline(
                self._thresholds["good"],
                color="#4CAF50",
                linestyle="--",
                linewidth=1,
                label=f"Umbral bueno ({self._thresholds['good']} dBm)",
                zorder=1,
            )
            self._legend = self._ax.legend(loc="upper left", fontsize=8, framealpha=0.92)
            aplicar_tema_leyenda(self._legend, self._theme)
        else:
            self._hline_fair.set_ydata([self._thresholds["fair"], self._thresholds["fair"]])
            self._hline_good.set_ydata([self._thresholds["good"], self._thresholds["good"]])
            self._hline_fair.set_label(f"Umbral débil ({self._thresholds['fair']} dBm)")
            self._hline_good.set_label(f"Umbral bueno ({self._thresholds['good']} dBm)")
            if self._legend:
                self._legend.remove()
            self._legend = self._ax.legend(loc="upper left", fontsize=8, framealpha=0.92)
            aplicar_tema_leyenda(self._legend, self._theme)

        titulo = f"Intensidad en el dispositivo — {self._ssid or '—'}"
        self._ax.set_title(titulo)

        if self._empty_text is None:
            self._empty_text = self._ax.text(
                0.5,
                0.5,
                "Selecciona una red y activa el monitoreo",
                transform=self._ax.transAxes,
                ha="center",
                va="center",
                color=c["text_muted"],
                zorder=0,
            )

    def actualizar(
        self,
        timestamps: list[float],
        values_dbm: list[int],
        ssid: str,
        thresholds: dict[str, int] | None = None,
        theme: str = "dark",
    ) -> None:
        if thresholds:
            self._thresholds = thresholds
        theme_changed = theme != self._theme
        self._theme = theme
        self._ssid = ssid

        if theme_changed:
            self._limpiar_artistas_dinamicos()
            self._hline_fair = None
            self._hline_good = None
            self._legend = None
            self._empty_text = None
            self._aplicar_estilo_base()

        hay_datos = bool(timestamps and values_dbm)

        if self._empty_text is not None:
            self._empty_text.set_visible(not hay_datos)

        if not hay_datos:
            self._limpiar_artistas_dinamicos()
            self._canvas.draw_idle()
            return

        if self._line is None:
            (self._line,) = self._ax.plot(
                timestamps, values_dbm, color="#1976D2", linewidth=1.8, zorder=3,
            )
            self._fill = self._ax.fill_between(
                timestamps, values_dbm, -100, alpha=0.15, color="#1976D2", zorder=2,
            )
        else:
            self._line.set_data(timestamps, values_dbm)
            if self._fill is not None:
                self._fill.remove()
            self._fill = self._ax.fill_between(
                timestamps, values_dbm, -100, alpha=0.15, color="#1976D2", zorder=2,
            )

        if timestamps:
            xmin, xmax = min(timestamps), max(timestamps)
            if xmin == xmax:
                self._ax.set_xlim(xmin - 1, xmax + 1)
            else:
                margin = max(0.5, (xmax - xmin) * 0.05)
                self._ax.set_xlim(xmin, xmax + margin)

        self._ax.set_title(f"Intensidad en el dispositivo — {ssid or '—'}")
        self._canvas.draw_idle()

    def _limpiar_artistas_dinamicos(self) -> None:
        if self._line is not None:
            self._line.remove()
            self._line = None
        if self._fill is not None:
            self._fill.remove()
            self._fill = None
