"""Gráfico de saturación por canal (actualización in-place)."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from wifind.servicios.analisis_canales import ResultadoAnalisisCanales
from wifind.ui.mpl_estilo import aplicar_tema_ejes, colores_tema


class GraficoCanales(QWidget):
    """Dos histogramas 2.4 / 5 GHz reutilizando una sola figura matplotlib."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = "dark"

        self._fig = Figure(figsize=(8, 3.5), dpi=100)
        self._ax24 = self._fig.add_subplot(121)
        self._ax5 = self._fig.add_subplot(122)
        self._canvas = FigureCanvasQTAgg(self._fig)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._fig.subplots_adjust(left=0.08, right=0.96, top=0.82, bottom=0.18, wspace=0.32)

    def actualizar(self, analysis: ResultadoAnalisisCanales, theme: str = "dark") -> None:
        self._theme = theme
        c = colores_tema(theme)
        self._fig.patch.set_facecolor(c["fig"])

        rec = analysis.canal_recomendado_24ghz or analysis.canal_recomendado_5ghz
        if rec:
            self._fig.suptitle(f"Canal recomendado: {rec}", fontsize=11, color=c["text"])
        else:
            self._fig.suptitle("")

        self._dibujar_banda(
            self._ax24,
            "2.4 GHz",
            analysis.conteos_24ghz,
            analysis.canal_recomendado_24ghz,
        )
        self._dibujar_banda(
            self._ax5,
            "5 GHz",
            analysis.conteos_5ghz,
            analysis.canal_recomendado_5ghz,
        )
        self._canvas.draw_idle()

    def _dibujar_banda(
        self,
        ax,
        titulo: str,
        conteos: dict[int, int],
        canal_recomendado: int | None,
    ) -> None:
        ax.clear()
        c = colores_tema(self._theme)
        active = {k: v for k, v in conteos.items() if v > 0}

        if active:
            channels = sorted(active.keys())
            values = [active[ch] for ch in channels]
            colores = [
                "#4CAF50" if ch == canal_recomendado else "#1976D2"
                for ch in channels
            ]
            ax.bar(channels, values, color=colores, alpha=0.85, width=0.8)
            ax.set_xlabel("Canal")
            ax.set_ylabel("Redes")
            if canal_recomendado and canal_recomendado in active:
                ax.axvline(
                    canal_recomendado,
                    color="#4CAF50",
                    linestyle="--",
                    linewidth=1.2,
                    alpha=0.9,
                )
        else:
            ax.text(
                0.5,
                0.5,
                "Sin datos",
                transform=ax.transAxes,
                ha="center",
                va="center",
                color=c["text_muted"],
            )

        ax.set_title(titulo)
        aplicar_tema_ejes(self._fig, ax, self._theme)
