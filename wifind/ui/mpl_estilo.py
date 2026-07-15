"""Estilo matplotlib coherente con el tema claro/oscuro de WiFind."""

from __future__ import annotations

from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.axes import Axes


def colores_tema(theme: str) -> dict[str, str]:
    if theme == "dark":
        return {
            "fig": "#2b2b2b",
            "ax": "#333333",
            "text": "#e0e0e0",
            "text_muted": "#aaaaaa",
            "grid": "#555555",
            "spine": "#666666",
            "legend_face": "#3c3c3c",
            "legend_edge": "#666666",
        }
    return {
        "fig": "#f5f5f5",
        "ax": "#ffffff",
        "text": "#212121",
        "text_muted": "#666666",
        "grid": "#cccccc",
        "spine": "#888888",
        "legend_face": "#ffffff",
        "legend_edge": "#cccccc",
    }


def aplicar_tema_ejes(fig: Figure, ax: Axes, theme: str = "dark") -> None:
    c = colores_tema(theme)
    fig.patch.set_facecolor(c["fig"])
    ax.set_facecolor(c["ax"])
    ax.title.set_color(c["text"])
    ax.xaxis.label.set_color(c["text"])
    ax.yaxis.label.set_color(c["text"])
    ax.tick_params(colors=c["text"])
    for spine in ax.spines.values():
        spine.set_color(c["spine"])
    ax.grid(True, linestyle="--", alpha=0.35, color=c["grid"])


def aplicar_tema_ejes_multiples(fig: Figure, axes, theme: str = "dark") -> None:
    c = colores_tema(theme)
    fig.patch.set_facecolor(c["fig"])
    for ax in axes:
        ax.set_facecolor(c["ax"])
        ax.title.set_color(c["text"])
        ax.xaxis.label.set_color(c["text"])
        ax.yaxis.label.set_color(c["text"])
        ax.tick_params(colors=c["text"])
        for spine in ax.spines.values():
            spine.set_color(c["spine"])
        ax.grid(True, linestyle="--", alpha=0.35, color=c["grid"])


def aplicar_tema_leyenda(legend: Legend, theme: str = "dark") -> None:
    c = colores_tema(theme)
    frame = legend.get_frame()
    frame.set_facecolor(c["legend_face"])
    frame.set_edgecolor(c["legend_edge"])
    for text in legend.get_texts():
        text.set_color(c["text"])


def aplicar_tema_colorbar(cbar: Colorbar, theme: str = "dark") -> None:
    c = colores_tema(theme)
    cbar.ax.yaxis.label.set_color(c["text"])
    cbar.ax.yaxis.set_tick_params(color=c["text"])
    for label in cbar.ax.get_yticklabels():
        label.set_color(c["text"])
    cbar.outline.set_edgecolor(c["spine"])
