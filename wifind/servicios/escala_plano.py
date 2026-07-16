"""Utilidades de escala del plano (px ↔ metros) y métricas derivadas."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from wifind.modelos.sesion import CalibracionPlanta, NivelPlanta
from wifind.servicios.cobertura import EstadisticasCobertura


@dataclass
class MetricasEscala:
    calibrado: bool
    pixels_per_meter: float
    ancho_m: float | None
    alto_m: float | None
    area_total_m2: float | None
    area_buena_m2: float | None
    area_debil_m2: float | None
    densidad_puntos_por_m2: float | None
    n_puntos: int


def esta_calibrado(cal: CalibracionPlanta) -> bool:
    return cal.pixels_per_meter > 0 and cal.real_length_m > 0


def px_a_metros(dist_px: float, cal: CalibracionPlanta) -> float | None:
    if not esta_calibrado(cal):
        return None
    return dist_px / cal.pixels_per_meter


def metros_a_px(dist_m: float, cal: CalibracionPlanta) -> float | None:
    if not esta_calibrado(cal):
        return None
    return dist_m * cal.pixels_per_meter


def distancia_px(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def distancia_metros(
    x1: float, y1: float, x2: float, y2: float, cal: CalibracionPlanta
) -> float | None:
    return px_a_metros(distancia_px(x1, y1, x2, y2), cal)


def formatear_longitud(metros: float | None, units: str = "m") -> str:
    if metros is None:
        return "—"
    if units == "ft":
        return f"{metros / 0.3048:.2f} ft"
    return f"{metros:.2f} m"


def formatear_area(m2: float | None, units: str = "m") -> str:
    if m2 is None:
        return "—"
    if units == "ft":
        return f"{m2 / (0.3048 ** 2):.1f} ft²"
    return f"{m2:.1f} m²"


def calcular_metricas_escala(
    floor: NivelPlanta,
    stats: EstadisticasCobertura | None = None,
) -> MetricasEscala:
    cal = floor.calibration
    n = len(floor.measurements)
    if not esta_calibrado(cal):
        return MetricasEscala(
            calibrado=False,
            pixels_per_meter=0.0,
            ancho_m=None,
            alto_m=None,
            area_total_m2=None,
            area_buena_m2=None,
            area_debil_m2=None,
            densidad_puntos_por_m2=None,
            n_puntos=n,
        )

    ppm = cal.pixels_per_meter
    ancho_m = floor.x_max / ppm
    alto_m = floor.y_max / ppm
    area_total = ancho_m * alto_m

    area_buena = None
    area_debil = None
    if stats is not None and area_total > 0:
        area_buena = area_total * (stats.porcentaje_bueno / 100.0)
        area_debil = area_total * (stats.porcentaje_debil / 100.0)

    densidad = (n / area_total) if area_total > 0 else None

    return MetricasEscala(
        calibrado=True,
        pixels_per_meter=ppm,
        ancho_m=ancho_m,
        alto_m=alto_m,
        area_total_m2=area_total,
        area_buena_m2=area_buena,
        area_debil_m2=area_debil,
        densidad_puntos_por_m2=densidad,
        n_puntos=n,
    )


def mascara_dentro_radio_m(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    centro_x: float,
    centro_y: float,
    radio_m: float,
    cal: CalibracionPlanta,
) -> np.ndarray | None:
    """Máscara booleana de celdas dentro de un radio en metros alrededor de un punto."""
    radio_px = metros_a_px(radio_m, cal)
    if radio_px is None or radio_px <= 0:
        return None
    dx = grid_x - centro_x
    dy = grid_y - centro_y
    return (dx * dx + dy * dy) <= (radio_px * radio_px)
