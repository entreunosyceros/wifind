"""Evaluación de cobertura WiFi por habitación del plano."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from matplotlib.path import Path

from wifind.mapa_calor import valor_visual_a_dbm
from wifind.modelos.medicion import Habitacion
from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import NivelPlanta

# Clave interna → etiqueta en informe/UI
NIVELES_COBERTURA: dict[str, str] = {
    "excelente": "Excelente",
    "buena": "Buena",
    "aceptable": "Aceptable",
    "deficiente": "Deficiente",
    "sin_datos": "Sin datos",
}

COLORES_NIVEL: dict[str, str] = {
    "excelente": "#2E7D32",
    "buena": "#558B2F",
    "aceptable": "#F9A825",
    "deficiente": "#C62828",
    "sin_datos": "#757575",
}


@dataclass
class EvaluacionHabitacion:
    habitacion: Habitacion
    nivel: str
    etiqueta: str
    media_dbm: float | None
    n_celdas: int


def clasificar_dbm(dbm: float, prefs: PreferenciasApp) -> str:
    if dbm >= prefs.threshold_excellent:
        return "excelente"
    if dbm >= prefs.threshold_good:
        return "buena"
    if dbm >= prefs.threshold_fair:
        return "aceptable"
    return "deficiente"


def mascara_dentro_habitacion(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    habitacion: Habitacion,
) -> np.ndarray:
    if len(habitacion.vertices) < 3:
        return np.zeros(grid_x.shape, dtype=bool)
    path = Path(habitacion.vertices)
    pts = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    return path.contains_points(pts).reshape(grid_x.shape)


def evaluar_habitacion(
    habitacion: Habitacion,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grid_z: np.ndarray,
    prefs: PreferenciasApp,
) -> EvaluacionHabitacion:
    mask = mascara_dentro_habitacion(grid_x, grid_y, habitacion)
    valid = mask & np.isfinite(grid_z)
    n = int(np.count_nonzero(valid))
    if n == 0:
        return EvaluacionHabitacion(
            habitacion=habitacion,
            nivel="sin_datos",
            etiqueta=NIVELES_COBERTURA["sin_datos"],
            media_dbm=None,
            n_celdas=0,
        )
    media = float(np.mean(valor_visual_a_dbm(grid_z[valid])))
    nivel = clasificar_dbm(media, prefs)
    return EvaluacionHabitacion(
        habitacion=habitacion,
        nivel=nivel,
        etiqueta=NIVELES_COBERTURA[nivel],
        media_dbm=round(media, 1),
        n_celdas=n,
    )


def evaluar_habitaciones_planta(
    floor: NivelPlanta,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    grid_z: np.ndarray,
    prefs: PreferenciasApp,
) -> list[EvaluacionHabitacion]:
    return [
        evaluar_habitacion(h, grid_x, grid_y, grid_z, prefs)
        for h in floor.habitaciones
    ]
