"""Motor de recorridos automáticos y survey por waypoints."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from wifind.modelos.medicion import Medicion, PuntoRuta


class ModoRecorrido(str, Enum):
    IDLE = "idle"
    AUTO_WALK = "auto_walk"
    WAYPOINT = "waypoint"


@dataclass
class EstadisticasTramoRuta:
    from_index: int
    to_index: int
    from_x: float
    from_y: float
    to_x: float
    to_y: float
    distance_m: float
    measurement_count: int
    signal_avg_dbm: float | None
    signal_min_dbm: int | None
    signal_max_dbm: int | None


@dataclass
class MotorRecorrido:
    """
    Gestiona recorridos de medición en el mapa.

    - Modo auto-walk: avanza en Y cada intervalo configurable.
    - Modo waypoint: el usuario registra señal al llegar a cada punto.
    """

    interval_sec: float = 3.0
    step_y: float = 1.0
    advance_y: bool = True
    mode: ModoRecorrido = ModoRecorrido.IDLE
    current_x: float = 0.0
    current_y: float = 0.0
    waypoints: list[PuntoRuta] = field(default_factory=list)
    measurements: list[Medicion] = field(default_factory=list)
    _last_tick: float = field(default_factory=time.time, repr=False)
    _next_waypoint_index: int = 0

    def iniciar_recorrido_auto(self, x: float, y: float) -> None:
        """Inicia un recorrido automático desde la posición indicada."""
        self.mode = ModoRecorrido.AUTO_WALK
        self.current_x = x
        self.current_y = y
        self._last_tick = time.time()
        self._next_waypoint_index = 0

    def iniciar_recorrido_waypoints(self, waypoints: list[PuntoRuta] | None = None) -> None:
        """Inicia survey por waypoints predefinidos en el mapa."""
        self.mode = ModoRecorrido.WAYPOINT
        if waypoints is not None:
            self.waypoints = list(waypoints)
        self._next_waypoint_index = 0
        for waypoint in self.waypoints:
            waypoint.registered = False
            waypoint.signal_dbm = None

    def stop(self) -> None:
        """Detiene el recorrido activo."""
        self.mode = ModoRecorrido.IDLE

    @property
    def is_active(self) -> bool:
        return self.mode != ModoRecorrido.IDLE

    @property
    def punto_ruta_actual(self) -> PuntoRuta | None:
        if self.mode != ModoRecorrido.WAYPOINT or self._next_waypoint_index >= len(self.waypoints):
            return None
        return self.waypoints[self._next_waypoint_index]

    def debe_muestrear(self) -> bool:
        """Indica si ha transcurrido el intervalo y corresponde medir."""
        if self.mode != ModoRecorrido.AUTO_WALK:
            return False
        return (time.time() - self._last_tick) >= self.interval_sec

    def tick(self) -> tuple[float, float] | None:
        """
        Avanza el recorrido automático si corresponde.

        Devuelve la posición (x, y) donde registrar medición, o None.
        """
        if not self.debe_muestrear():
            return None
        position = (self.current_x, self.current_y)
        self._last_tick = time.time()
        if self.advance_y:
            self.current_y += self.step_y
        return position

    def anadir_medicion(self, measurement: Medicion) -> None:
        """Registra una medición en el recorrido activo."""
        self.measurements.append(measurement)
        if self.mode == ModoRecorrido.WAYPOINT:
            waypoint = self.punto_ruta_actual
            if waypoint is not None:
                waypoint.registered = True
                waypoint.signal_dbm = measurement.signal_dbm
                self._next_waypoint_index += 1
                if self._next_waypoint_index >= len(self.waypoints):
                    self.stop()

    def registrar_en_punto_ruta(self, measurement: Medicion) -> bool:
        """Registra señal en el waypoint actual del modo waypoint."""
        if self.mode != ModoRecorrido.WAYPOINT or self.punto_ruta_actual is None:
            return False
        self.anadir_medicion(measurement)
        return True

    def calcular_tramos_ruta(self) -> list[EstadisticasTramoRuta]:
        """
        Calcula estadísticas por tramo entre waypoints consecutivos.

        Asigna mediciones al tramo cuyo waypoint destino está más cercano.
        """
        if len(self.waypoints) < 2:
            return []

        segments: list[EstadisticasTramoRuta] = []
        for index in range(len(self.waypoints) - 1):
            start = self.waypoints[index]
            end = self.waypoints[index + 1]
            midpoint_x = (start.x + end.x) / 2.0
            midpoint_y = (start.y + end.y) / 2.0
            segment_measurements = [
                m
                for m in self.measurements
                if _distance(m.x, m.y, midpoint_x, midpoint_y)
                <= _distance(m.x, m.y, start.x, start.y)
                or _distance(m.x, m.y, midpoint_x, midpoint_y)
                <= _distance(m.x, m.y, end.x, end.y)
            ]
            signals = [m.signal_dbm for m in segment_measurements]
            distance = _distance(start.x, start.y, end.x, end.y)
            segments.append(
                EstadisticasTramoRuta(
                    from_index=index,
                    to_index=index + 1,
                    from_x=start.x,
                    from_y=start.y,
                    to_x=end.x,
                    to_y=end.y,
                    distance_m=round(distance, 2),
                    measurement_count=len(signals),
                    signal_avg_dbm=round(sum(signals) / len(signals), 1) if signals else None,
                    signal_min_dbm=min(signals) if signals else None,
                    signal_max_dbm=max(signals) if signals else None,
                )
            )
        return segments


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
