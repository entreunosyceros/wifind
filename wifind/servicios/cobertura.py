"""Estadísticas de cobertura a partir del mapa interpolado."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wifind.mapa_calor import dbm_a_valor_visual


@dataclass
class EstadisticasCobertura:
    porcentaje_bueno: float
    porcentaje_debil: float
    mascara_debil: np.ndarray


def calcular_estadisticas_cobertura(
    grid_z: np.ndarray,
    x_max: float,
    y_max: float,
    weak_threshold_dbm: int,
) -> EstadisticasCobertura:
    """
    Calcula porcentajes de cobertura buena/débil sobre la malla interpolada.

    ``grid_z`` contiene valores normalizados 0..1 (ver ``dbm_a_valor_visual``).
    Las celdas NaN (sin datos) se excluyen del cálculo.
    """
    del x_max, y_max  # reservados para extensiones con área ponderada

    weak_display = dbm_a_valor_visual(weak_threshold_dbm)
    valid = np.isfinite(grid_z)
    total = int(np.count_nonzero(valid))

    if total == 0:
        empty_mask = np.zeros_like(grid_z, dtype=bool)
        return EstadisticasCobertura(porcentaje_bueno=0.0, porcentaje_debil=0.0, mascara_debil=empty_mask)

    mascara_debil = valid & (grid_z < weak_display)
    weak_count = int(np.count_nonzero(mascara_debil))
    good_count = total - weak_count

    return EstadisticasCobertura(
        porcentaje_bueno=round(100.0 * good_count / total, 1),
        porcentaje_debil=round(100.0 * weak_count / total, 1),
        mascara_debil=mascara_debil,
    )
