"""Generación de mapas de calor e interpolación de señal WiFi."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from matplotlib.figure import Figure

from wifind.modelos.medicion import (
    Habitacion,
    Medicion,
    Obstaculo,
    PuntoAcceso,
    color_tipo_ap,
    etiqueta_tipo_ap,
    marcador_tipo_ap,
)


# Compatibilidad
PuntoMedicion = Medicion

_COLORES_MATERIAL = {
    "pladur": "#C4A574",
    "ladrillo": "#A0522D",
    "hormigon": "#404040",
    "personalizado": "#6A5ACD",
}


def color_material(material: str) -> str:
    return _COLORES_MATERIAL.get(material, "#888888")


def segmentos_se_intersectan(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
) -> bool:
    """Comprueba si el segmento AB cruza el interior del segmento CD."""
    eps = 1e-9
    denom = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if abs(denom) < eps:
        return False
    t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denom
    u = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / denom
    return eps < t < 1 - eps and eps < u < 1 - eps


def rayo_cruza_obstaculo(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    obstaculo: Obstaculo,
) -> bool:
    """True si el rayo medición→píxel atraviesa el segmento de pared."""
    if max(ax, bx) < min(obstaculo.x1, obstaculo.x2) - 1e-9:
        return False
    if min(ax, bx) > max(obstaculo.x1, obstaculo.x2) + 1e-9:
        return False
    if max(ay, by) < min(obstaculo.y1, obstaculo.y2) - 1e-9:
        return False
    if min(ay, by) > max(obstaculo.y1, obstaculo.y2) + 1e-9:
        return False
    return segmentos_se_intersectan(
        ax, ay, bx, by,
        obstaculo.x1, obstaculo.y1, obstaculo.x2, obstaculo.y2,
    )


def calcular_atenuacion_rayo(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    obstaculos: Sequence[Obstaculo],
) -> float:
    """Suma la atenuación (dB) de todas las paredes que cruza el rayo."""
    total = 0.0
    for obs in obstaculos:
        if rayo_cruza_obstaculo(ax, ay, bx, by, obs):
            total += obs.atenuacion_db
    return total


def _dibujar_obstaculos(ax, obstaculos: Sequence[Obstaculo], zorder: int = 2) -> None:
    for obs in obstaculos:
        color = color_material(obs.material)
        ax.plot(
            [obs.x1, obs.x2],
            [obs.y1, obs.y2],
            color=color,
            linewidth=4,
            solid_capstyle="round",
            zorder=zorder,
        )
        mx = (obs.x1 + obs.x2) / 2
        my = (obs.y1 + obs.y2) / 2
        ax.annotate(
            f"{obs.atenuacion_db:.0f} dB",
            (mx, my),
            fontsize=6,
            ha="center",
            va="center",
            color="white",
            bbox={"facecolor": color, "alpha": 0.85, "edgecolor": "none", "pad": 1},
            zorder=zorder + 1,
        )


def _dibujar_puntos_acceso(
    ax,
    access_points: Sequence[PuntoAcceso],
    theme: str = "dark",
    zorder: int = 6,
) -> None:
    """Dibuja marcadores de router / AP / repetidor con etiqueta."""
    if not access_points:
        return
    from wifind.ui.mpl_estilo import colores_tema

    c = colores_tema(theme)
    tipos_en_leyenda: set[str] = set()
    for ap in access_points:
        color = color_tipo_ap(ap.tipo)
        marker = marcador_tipo_ap(ap.tipo)
        label = etiqueta_tipo_ap(ap.tipo) if ap.tipo not in tipos_en_leyenda else None
        tipos_en_leyenda.add(ap.tipo)
        ax.scatter(
            [ap.x],
            [ap.y],
            c=color,
            s=160,
            marker=marker,
            edgecolors="white",
            linewidths=1.2,
            zorder=zorder,
            label=label,
        )
        ax.annotate(
            f"{ap.nombre}" + (" *" if getattr(ap, "es_referencia", False) else ""),
            (ap.x, ap.y),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color=color,
            bbox={
                "facecolor": c["ax"],
                "alpha": 0.88,
                "edgecolor": color,
                "boxstyle": "round,pad=0.25",
                "linewidth": 1.0,
            },
            zorder=zorder + 1,
        )


def _dibujar_cobertura_respecto_router(
    ax,
    router: PuntoAcceso,
    radios_m: Sequence[float],
    cal,
    units: str = "m",
    zorder: int = 5,
) -> None:
    """Círculos concéntricos de distancia alrededor del router de referencia."""
    from matplotlib.patches import Circle

    from wifind.servicios.escala_plano import esta_calibrado, formatear_longitud, metros_a_px

    if not esta_calibrado(cal):
        for r in radios_m:
            circ = Circle(
                (router.x, router.y),
                r,
                fill=False,
                edgecolor="#C62828",
                linewidth=1.0,
                linestyle=":",
                alpha=0.55,
                zorder=zorder,
            )
            ax.add_patch(circ)
            ax.annotate(
                f"{r:.0f}",
                (router.x + r, router.y),
                fontsize=7,
                color="#C62828",
                zorder=zorder + 1,
            )
        return

    for r_m in radios_m:
        r_px = metros_a_px(r_m, cal)
        if r_px is None or r_px <= 0:
            continue
        circ = Circle(
            (router.x, router.y),
            r_px,
            fill=False,
            edgecolor="#C62828",
            linewidth=1.2,
            linestyle="--",
            alpha=0.7,
            zorder=zorder,
        )
        ax.add_patch(circ)
        ax.annotate(
            formatear_longitud(r_m, units),
            (router.x + r_px * 0.7, router.y + r_px * 0.7),
            fontsize=7,
            color="#C62828",
            fontweight="bold",
            zorder=zorder + 1,
        )


def _dibujar_habitaciones(
    ax,
    habitaciones: Sequence[Habitacion],
    etiquetas: dict[str, str] | None = None,
    theme: str = "dark",
    zorder: int = 2,
) -> None:
    """Dibuja zonas de habitación con relleno suave y nombre."""
    if not habitaciones:
        return
    from matplotlib.patches import Polygon

    from wifind.ui.mpl_estilo import colores_tema

    c = colores_tema(theme)
    etiquetas = etiquetas or {}
    for hab in habitaciones:
        if len(hab.vertices) < 3:
            continue
        poly = Polygon(
            hab.vertices,
            closed=True,
            facecolor=hab.color,
            edgecolor=hab.color,
            linewidth=1.8,
            alpha=0.18,
            zorder=zorder,
        )
        ax.add_patch(poly)
        xs = [v[0] for v in hab.vertices] + [hab.vertices[0][0]]
        ys = [v[1] for v in hab.vertices] + [hab.vertices[0][1]]
        ax.plot(xs, ys, color=hab.color, linewidth=1.5, alpha=0.85, zorder=zorder + 1)
        cx, cy = hab.centro()
        texto = hab.nombre
        extra = etiquetas.get(hab.id)
        if extra:
            texto = f"{hab.nombre}\n{extra}"
        ax.annotate(
            texto,
            (cx, cy),
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color=c["text"],
            bbox={
                "facecolor": c["ax"],
                "alpha": 0.75,
                "edgecolor": hab.color,
                "boxstyle": "round,pad=0.3",
                "linewidth": 1.0,
            },
            zorder=zorder + 2,
        )


def dbm_a_valor_visual(dbm: int) -> float:
    return float(np.clip((dbm + 100) / 70.0, 0.0, 1.0))


def valor_visual_a_dbm(value: float) -> float:
    return value * 70.0 - 100.0


def interpolar_senal(
    points: Sequence[Medicion],
    grid_size: int = 80,
    x_max: float = 10.0,
    y_max: float = 10.0,
    funcion_rbf: str = "multiquadric",
    obstaculos: Sequence[Obstaculo] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Interpola la señal medida en una malla regular.

    Sin obstáculos usa RBF (transiciones suaves). Con paredes dibujadas aplica
    IDW ponderado restando la atenuación acumulada en el rayo medición→píxel.
    """
    xi = np.linspace(0, x_max, grid_size)
    yi = np.linspace(0, y_max, grid_size)
    grid_x, grid_y = np.meshgrid(xi, yi)

    if not points:
        return grid_x, grid_y, np.full_like(grid_x, np.nan)

    xs = np.array([p.x for p in points], dtype=float)
    ys = np.array([p.y for p in points], dtype=float)
    senales_dbm = np.array([p.signal_dbm for p in points], dtype=float)

    if obstaculos:
        grid_z = _interpolar_senal_con_obstaculos(xs, ys, senales_dbm, grid_x, grid_y, obstaculos)
        grid_z = np.clip(grid_z, 0.0, 1.0)
        return grid_x, grid_y, grid_z

    valores = np.array([dbm_a_valor_visual(p.signal_dbm) for p in points], dtype=float)
    n = len(valores)
    if n == 1:
        grid_z = np.full_like(grid_x, valores[0], dtype=float)
        return grid_x, grid_y, grid_z

    from scipy.interpolate import Rbf

    # Pocos puntos: RBF lineal; más puntos: multicuadrática (transiciones más suaves).
    if n < 4:
        funcion = "linear"
        suavizado = 0.1
    elif n < 8:
        funcion = "linear" if funcion_rbf == "linear" else "thin_plate"
        suavizado = 0.08
    else:
        funcion = funcion_rbf
        suavizado = 0.05

    try:
        rbf = Rbf(xs, ys, valores, function=funcion, smooth=suavizado)
        grid_z = rbf(grid_x.ravel(), grid_y.ravel()).reshape(grid_x.shape)
    except Exception:
        grid_z = _interpolar_senal_idw(xs, ys, valores, grid_x, grid_y)

    grid_z = np.clip(grid_z, 0.0, 1.0)
    return grid_x, grid_y, grid_z


def _interpolar_senal_con_obstaculos(
    xs: np.ndarray,
    ys: np.ndarray,
    senales_dbm: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    obstaculos: Sequence[Obstaculo],
) -> np.ndarray:
    """IDW con señal efectiva = medición − atenuación de paredes en el rayo."""
    flat_x = grid_x.ravel()
    flat_y = grid_y.ravel()
    n_cells = flat_x.size
    grid_z = np.zeros(n_cells, dtype=float)
    peso_total = np.zeros(n_cells, dtype=float)

    for mx, my, sig_dbm in zip(xs, ys, senales_dbm, strict=True):
        att = np.zeros(n_cells, dtype=float)
        for obs in obstaculos:
            for i in range(n_cells):
                if rayo_cruza_obstaculo(mx, my, flat_x[i], flat_y[i], obs):
                    att[i] += obs.atenuacion_db

        eff_dbm = np.clip(sig_dbm - att, -100.0, -30.0)
        eff_val = np.clip((eff_dbm + 100.0) / 70.0, 0.0, 1.0)

        dist = np.sqrt((flat_x - mx) ** 2 + (flat_y - my) ** 2)
        dist = np.maximum(dist, 0.05)
        pesos = 1.0 / dist**2
        grid_z += pesos * eff_val
        peso_total += pesos

    return (grid_z / np.maximum(peso_total, 1e-9)).reshape(grid_x.shape)


def _interpolar_senal_idw(
    xs: np.ndarray,
    ys: np.ndarray,
    valores: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
) -> np.ndarray:
    """Respaldo IDW por si RBF no converge con la geometría de los puntos."""
    grid_z = np.zeros_like(grid_x, dtype=float)
    peso_total = np.zeros_like(grid_x, dtype=float)

    for x, y, valor in zip(xs, ys, valores, strict=True):
        dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
        dist = np.maximum(dist, 0.05)
        pesos = 1.0 / dist**2
        grid_z += pesos * valor
        peso_total += pesos

    return grid_z / np.maximum(peso_total, 1e-9)


def dibujar_mapa_calor_en(
    fig: Figure,
    ax,
    points: Sequence[Medicion],
    ssid: str,
    x_max: float = 10.0,
    y_max: float = 10.0,
    floor_plan_path: str | Path | None = None,
    weak_threshold_dbm: int = -70,
    show_weak_zones: bool = True,
    waypoints: Sequence | None = None,
    calibration_line: tuple[float, float, float, float] | None = None,
    obstaculos: Sequence[Obstaculo] | None = None,
    access_points: Sequence[PuntoAcceso] | None = None,
    habitaciones: Sequence[Habitacion] | None = None,
    etiquetas_habitacion: dict[str, str] | None = None,
    router_referencia: PuntoAcceso | None = None,
    radios_router_m: Sequence[float] | None = None,
    calibracion=None,
    unit_suffix: str = " m",
    colormap: str = "RdYlGn",
    theme: str = "dark",
) -> None:
    """Dibuja el mapa de calor en ejes matplotlib ya creados."""
    import matplotlib.image as mpimg

    from wifind.ui.mpl_estilo import (
        aplicar_tema_colorbar,
        aplicar_tema_ejes,
        aplicar_tema_leyenda,
        colores_tema,
    )

    obstaculos = obstaculos or []
    access_points = access_points or []
    habitaciones = habitaciones or []
    c = colores_tema(theme)
    grid_x, grid_y, grid_z = interpolar_senal(
        points, x_max=x_max, y_max=y_max, obstaculos=obstaculos or None,
    )

    has_floor_plan = False
    if floor_plan_path:
        plan_path = Path(floor_plan_path)
        if plan_path.is_file():
            try:
                plan_img = mpimg.imread(str(plan_path))
                ax.imshow(
                    plan_img,
                    origin="upper",
                    extent=(0, x_max, 0, y_max),
                    aspect="auto",
                    alpha=0.92,
                    zorder=0,
                )
                has_floor_plan = True
            except Exception:
                pass

    if calibration_line:
        x1, y1, x2, y2 = calibration_line
        ax.plot([x1, x2], [y1, y2], "b-", linewidth=2, zorder=2, label="Calibración")

    if habitaciones:
        _dibujar_habitaciones(
            ax, habitaciones, etiquetas=etiquetas_habitacion, theme=theme, zorder=2
        )

    if obstaculos:
        _dibujar_obstaculos(ax, obstaculos, zorder=3)

    im = None
    if points:
        heatmap_alpha = 0.55 if has_floor_plan else 0.85
        im = ax.imshow(
            grid_z,
            origin="lower",
            extent=(0, x_max, 0, y_max),
            cmap=colormap,
            vmin=0.0,
            vmax=1.0,
            aspect="auto",
            alpha=heatmap_alpha,
            zorder=1,
        )

        if show_weak_zones and not np.all(np.isnan(grid_z)):
            mascara_debil = valor_visual_a_dbm(grid_z) < weak_threshold_dbm
            ax.contourf(
                grid_x,
                grid_y,
                mascara_debil.astype(float),
                levels=[0.5, 1.5],
                colors=[(1, 0, 0, 0.25)],
                zorder=2,
            )

        ax.scatter(
            [p.x for p in points],
            [p.y for p in points],
            c=[p.signal_dbm for p in points],
            cmap=colormap,
            vmin=-100,
            vmax=-30,
            edgecolors="black",
            linewidths=0.6,
            s=55,
            zorder=3,
        )
        for point in points:
            label = f"{point.signal_dbm}"
            if point.notes:
                label += f"\n{point.notes[:12]}"
            ax.annotate(
                label,
                (point.x, point.y),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=7,
                zorder=4,
            )
    elif not has_floor_plan:
        ax.text(
            0.5,
            0.5,
            "Clic en el mapa o usa coordenadas\npara registrar mediciones",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color=c["text_muted"],
        )
    else:
        ax.text(
            0.5,
            0.02,
            "Clic en el plano para registrar mediciones",
            transform=ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=9,
            color=c["text"],
            bbox={"facecolor": c["ax"], "alpha": 0.85, "edgecolor": c["spine"], "pad": 4},
            zorder=5,
        )

    if waypoints:
        wx = [w.x for w in waypoints]
        wy = [w.y for w in waypoints]
        ax.plot(wx, wy, "b--", alpha=0.7, zorder=2, label="Ruta survey")
        ax.scatter(wx, wy, c="blue", s=40, zorder=3, marker="s")
        for wp in waypoints:
            if wp.registered and wp.signal_dbm is not None:
                ax.annotate(
                    str(wp.signal_dbm),
                    (wp.x, wp.y),
                    textcoords="offset points",
                    xytext=(0, -10),
                    ha="center",
                    fontsize=7,
                    color="blue",
                )

    if access_points:
        _dibujar_puntos_acceso(ax, access_points, theme=theme)

    if router_referencia is not None and radios_router_m and calibracion is not None:
        units = "ft" if "ft" in unit_suffix.lower() else "m"
        _dibujar_cobertura_respecto_router(
            ax,
            router_referencia,
            radios_router_m,
            calibracion,
            units=units,
        )

    ax.set_xlim(0, x_max)
    ax.set_ylim(0, y_max)
    ax.set_xlabel(f"X ({unit_suffix.strip()})")
    ax.set_ylabel(f"Y ({unit_suffix.strip()})")
    ax.set_title(f"Mapa de calor — {ssid or 'Red WiFi'}")
    aplicar_tema_ejes(fig, ax, theme)

    if im is not None:
        fig.subplots_adjust(left=0.10, right=0.84, top=0.92, bottom=0.10)
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Intensidad relativa")
        aplicar_tema_colorbar(cbar, theme)
    else:
        fig.subplots_adjust(left=0.10, right=0.97, top=0.92, bottom=0.10)

    if calibration_line or waypoints or access_points:
        legend = ax.legend(loc="upper right", fontsize=8)
        aplicar_tema_leyenda(legend, theme)


def dibujar_mapa_calor_comparacion_en(
    fig: Figure,
    measurements_by_ssid: dict[str, list[Medicion]],
    x_max: float,
    y_max: float,
    floor_plan_path: str | Path | None = None,
    obstaculos: Sequence[Obstaculo] | None = None,
    theme: str = "dark",
    access_points: Sequence[PuntoAcceso] | None = None,
    habitaciones: Sequence[Habitacion] | None = None,
) -> None:
    """Dibuja varios mapas de calor en subplots de una figura existente."""
    import matplotlib.image as mpimg

    from wifind.ui.mpl_estilo import aplicar_tema_ejes, colores_tema

    ssids = list(measurements_by_ssid.keys())
    n = max(len(ssids), 1)
    cols = min(n, 2)
    rows = (n + cols - 1) // cols
    c = colores_tema(theme)
    cmaps = ["RdYlGn", "viridis", "plasma", "cividis"]
    access_points = access_points or []
    habitaciones = habitaciones or []

    for idx, ssid in enumerate(ssids):
        ax = fig.add_subplot(rows, cols, idx + 1)
        pts = measurements_by_ssid[ssid]
        grid_x, grid_y, grid_z = interpolar_senal(
            pts, x_max=x_max, y_max=y_max, obstaculos=obstaculos,
        )
        if floor_plan_path and Path(floor_plan_path).is_file():
            try:
                plan_img = mpimg.imread(str(floor_plan_path))
                ax.imshow(
                    plan_img, origin="upper", extent=(0, x_max, 0, y_max),
                    aspect="auto", alpha=0.9,
                )
            except Exception:
                pass
        if habitaciones:
            _dibujar_habitaciones(ax, habitaciones, theme=theme, zorder=2)
        if obstaculos:
            _dibujar_obstaculos(ax, obstaculos, zorder=2)
        if pts:
            ax.imshow(
                grid_z, origin="lower", extent=(0, x_max, 0, y_max),
                cmap=cmaps[idx % len(cmaps)], alpha=0.7, vmin=0, vmax=1,
            )
            ax.scatter([p.x for p in pts], [p.y for p in pts], c="black", s=30)
        if access_points:
            _dibujar_puntos_acceso(ax, access_points, theme=theme)
        ax.set_title(ssid)
        ax.set_xlim(0, x_max)
        ax.set_ylim(0, y_max)
        aplicar_tema_ejes(fig, ax, theme)

    for idx in range(len(ssids), rows * cols):
        ax = fig.add_subplot(rows, cols, idx + 1)
        ax.axis("off")

    fig.suptitle("Comparación de redes WiFi", fontsize=12, color=c["text"])
    fig.subplots_adjust(left=0.06, right=0.97, top=0.88, bottom=0.10, hspace=0.35, wspace=0.25)


def construir_figura_mapa_calor(
    points: Sequence[Medicion],
    ssid: str,
    x_max: float = 10.0,
    y_max: float = 10.0,
    floor_plan_path: str | Path | None = None,
    weak_threshold_dbm: int = -70,
    show_weak_zones: bool = True,
    waypoints: Sequence | None = None,
    calibration_line: tuple[float, float, float, float] | None = None,
    obstaculos: Sequence[Obstaculo] | None = None,
    unit_suffix: str = " m",
    colormap: str = "RdYlGn",
    theme: str = "dark",
    access_points: Sequence[PuntoAcceso] | None = None,
    habitaciones: Sequence[Habitacion] | None = None,
    etiquetas_habitacion: dict[str, str] | None = None,
    router_referencia: PuntoAcceso | None = None,
    radios_router_m: Sequence[float] | None = None,
    calibracion=None,
) -> Figure:
    from matplotlib.figure import Figure as MplFigure

    fig = MplFigure(figsize=(6, 5), dpi=100)
    ax = fig.add_subplot(111)
    dibujar_mapa_calor_en(
        fig,
        ax,
        points,
        ssid,
        x_max=x_max,
        y_max=y_max,
        floor_plan_path=floor_plan_path,
        weak_threshold_dbm=weak_threshold_dbm,
        show_weak_zones=show_weak_zones,
        waypoints=waypoints,
        calibration_line=calibration_line,
        obstaculos=obstaculos,
        access_points=access_points,
        habitaciones=habitaciones,
        etiquetas_habitacion=etiquetas_habitacion,
        router_referencia=router_referencia,
        radios_router_m=radios_router_m,
        calibracion=calibracion,
        unit_suffix=unit_suffix,
        colormap=colormap,
        theme=theme,
    )
    return fig


def construir_figura_mapa_calor_multiple(
    measurements_by_ssid: dict[str, list[Medicion]],
    x_max: float,
    y_max: float,
    floor_plan_path: str | Path | None = None,
    weak_threshold_dbm: int = -70,
    obstaculos: Sequence[Obstaculo] | None = None,
    unit_suffix: str = " m",
    theme: str = "dark",
) -> Figure:
    from matplotlib.figure import Figure as MplFigure

    ssids = list(measurements_by_ssid.keys())
    n = max(len(ssids), 1)
    cols = min(n, 2)
    rows = (n + cols - 1) // cols
    fig = MplFigure(figsize=(6 * cols, 5 * rows), dpi=100)
    dibujar_mapa_calor_comparacion_en(
        fig,
        measurements_by_ssid,
        x_max,
        y_max,
        floor_plan_path,
        obstaculos,
        theme,
    )
    return fig


def construir_figura_intensidad(
    timestamps: list[float],
    values_dbm: list[int],
    ssid: str,
    thresholds: dict[str, int] | None = None,
    theme: str = "dark",
) -> Figure:
    from matplotlib.figure import Figure as MplFigure

    from wifind.ui.mpl_estilo import aplicar_tema_ejes, aplicar_tema_leyenda, colores_tema

    t = thresholds or {"good": -50, "fair": -70}
    c = colores_tema(theme)
    fig = MplFigure(figsize=(6, 3.5), dpi=100)
    ax = fig.add_subplot(111)
    if timestamps and values_dbm:
        ax.plot(timestamps, values_dbm, color="#1976D2", linewidth=1.8)
        ax.fill_between(timestamps, values_dbm, -100, alpha=0.15, color="#1976D2")
        ax.axhline(
            t["fair"], color="#FF9800", linestyle="--", linewidth=1,
            label=f"Umbral débil ({t['fair']} dBm)",
        )
        ax.axhline(
            t["good"], color="#4CAF50", linestyle="--", linewidth=1,
            label=f"Umbral bueno ({t['good']} dBm)",
        )
        legend = ax.legend(loc="upper left", fontsize=8, framealpha=0.92)
        aplicar_tema_leyenda(legend, theme)
    else:
        ax.text(
            0.5,
            0.5,
            "Selecciona una red y activa el monitoreo",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=c["text_muted"],
        )

    ax.set_ylim(-100, -30)
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Señal (dBm)")
    ax.set_title(f"Intensidad en el dispositivo — {ssid or '—'}")
    aplicar_tema_ejes(fig, ax, theme)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.88, bottom=0.18)
    return fig


def construir_figura_canales(analysis, theme: str = "dark") -> Figure:
    from matplotlib.figure import Figure as MplFigure

    from wifind.ui.mpl_estilo import aplicar_tema_ejes, colores_tema

    c = colores_tema(theme)
    fig = MplFigure(figsize=(8, 3.5), dpi=100)
    ax24 = fig.add_subplot(121)
    ax5 = fig.add_subplot(122)

    for ax, band, counts, rec in [
        (ax24, "2.4 GHz", analysis.conteos_24ghz, analysis.canal_recomendado_24ghz),
        (ax5, "5 GHz", analysis.conteos_5ghz, analysis.canal_recomendado_5ghz),
    ]:
        active = {k: v for k, v in counts.items() if v > 0}
        if active:
            channels = sorted(active.keys())
            values = [active[ch] for ch in channels]
            bar_colors = ["#4CAF50" if ch == rec else "#1976D2" for ch in channels]
            ax.bar(channels, values, color=bar_colors, alpha=0.85, width=0.8)
            ax.set_xlabel("Canal")
            ax.set_ylabel("Redes")
            ax.set_title(band)
            if rec and rec in active:
                ax.axvline(rec, color="#4CAF50", linestyle="--", linewidth=1.2, alpha=0.9)
        else:
            ax.text(
                0.5, 0.5, "Sin datos", transform=ax.transAxes,
                ha="center", va="center", color=c["text_muted"],
            )
            ax.set_title(band)
        aplicar_tema_ejes(fig, ax, theme)

    rec = analysis.canal_recomendado_24ghz or analysis.canal_recomendado_5ghz
    if rec:
        fig.suptitle(f"Canal recomendado: {rec}", fontsize=11, color=c["text"])
    fig.subplots_adjust(left=0.08, right=0.96, top=0.82, bottom=0.18, wspace=0.32)
    return fig


def construir_figura_historico(snapshots, theme: str = "dark") -> Figure:
    from matplotlib.figure import Figure as MplFigure

    from wifind.ui.mpl_estilo import aplicar_tema_ejes, aplicar_tema_leyenda, colores_tema

    c = colores_tema(theme)
    fig = MplFigure(figsize=(6, 3.5), dpi=100)
    ax = fig.add_subplot(111)
    if snapshots:
        times = [s.timestamp - snapshots[0].timestamp for s in snapshots]
        counts = [s.numero_redes for s in snapshots]
        avgs = [s.senal_media_dbm or 0 for s in snapshots]
        line_counts, = ax.plot(times, counts, label="Nº redes", color="#1976D2", linewidth=1.8)
        ax2 = ax.twinx()
        line_avg, = ax2.plot(times, avgs, label="Señal media (dBm)", color="#FF9800", linewidth=1.8)
        ax.set_xlabel("Tiempo (s)")
        ax.set_ylabel("Redes visibles")
        ax2.set_ylabel("dBm")
        ax2.tick_params(colors=c["text"])
        ax2.yaxis.label.set_color(c["text"])
        for spine in ax2.spines.values():
            spine.set_color(c["spine"])
        legend = ax.legend([line_counts, line_avg], [line_counts.get_label(), line_avg.get_label()],
                           loc="upper left", fontsize=8, framealpha=0.92)
        aplicar_tema_leyenda(legend, theme)
    else:
        ax.text(
            0.5, 0.5, "Sin histórico de escaneos", transform=ax.transAxes,
            ha="center", va="center", color=c["text_muted"],
        )
    ax.set_title("Histórico de escaneos")
    aplicar_tema_ejes(fig, ax, theme)
    fig.subplots_adjust(left=0.10, right=0.88, top=0.88, bottom=0.18)
    return fig
