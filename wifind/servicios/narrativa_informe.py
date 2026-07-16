"""Resumen ejecutivo en lenguaje natural para informes de cliente."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from wifind.modelos.dispositivo_red import DispositivoRed, RolDispositivo, TipoDispositivo
from wifind.modelos.medicion import PuntoAcceso
from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import NivelPlanta, SesionApp
from wifind.servicios.analisis_canales import ResultadoAnalisisCanales
from wifind.servicios.cobertura import EstadisticasCobertura
from wifind.servicios.escala_plano import esta_calibrado, formatear_longitud, px_a_metros
from wifind.servicios.habitaciones import EvaluacionHabitacion
from wifind.wifi.red import RedWifi


@dataclass
class ResumenEjecutivo:
    parrafos: list[str] = field(default_factory=list)
    recomendaciones: list[str] = field(default_factory=list)

    @property
    def tiene_contenido(self) -> bool:
        return bool(self.parrafos or self.recomendaciones)


def router_de_referencia(floor: NivelPlanta) -> PuntoAcceso | None:
    """Router marcado como referencia, o el primer marcador tipo router."""
    for ap in floor.access_points:
        if getattr(ap, "es_referencia", False):
            return ap
    for ap in floor.access_points:
        if ap.tipo == "router":
            return ap
    return None


def distancia_a_router_m(
    x: float, y: float, router: PuntoAcceso, floor: NivelPlanta
) -> float | None:
    dist_px = math.hypot(x - router.x, y - router.y)
    if esta_calibrado(floor.calibration):
        return px_a_metros(dist_px, floor.calibration)
    return dist_px


def _frase_canales(analysis: ResultadoAnalisisCanales) -> str | None:
    partes: list[str] = []
    if analysis.canal_recomendado_5ghz is not None:
        partes.append(f"el canal {analysis.canal_recomendado_5ghz} (5 GHz)")
    if analysis.canal_recomendado_24ghz is not None:
        partes.append(f"el canal {analysis.canal_recomendado_24ghz} (2,4 GHz)")
    if not partes:
        return None
    if len(partes) == 1:
        return f"El canal recomendado es {partes[0]}."
    return f"Los canales recomendados son {partes[0]} y {partes[1]}."


def _frase_cobertura(stats: EstadisticasCobertura | None) -> str | None:
    if stats is None:
        return None
    bueno = stats.porcentaje_bueno
    if bueno >= 85:
        cualidad = "excelente"
    elif bueno >= 70:
        cualidad = "buena"
    elif bueno >= 50:
        cualidad = "aceptable"
    else:
        cualidad = "mejorable"
    return (
        f"La cobertura es {cualidad} en el {bueno:.0f} % de la planta "
        f"({stats.porcentaje_debil:.0f} % con señal débil)."
    )


def _frase_habitaciones(
    evals: list[EvaluacionHabitacion],
    floor: NivelPlanta,
    units: str,
) -> tuple[str | None, list[str]]:
    if not evals:
        return None, []

    excelentes = [e for e in evals if e.nivel == "excelente"]
    buenas = [e for e in evals if e.nivel == "buena"]
    aceptables = [e for e in evals if e.nivel == "aceptable"]
    deficientes = [e for e in evals if e.nivel == "deficiente"]
    recomendaciones: list[str] = []
    router = router_de_referencia(floor)
    frags: list[str] = []

    if deficientes:
        if len(deficientes) == 1:
            ev = deficientes[0]
            cx, cy = ev.habitacion.centro()
            extra = ""
            if router is not None:
                dist = distancia_a_router_m(cx, cy, router, floor)
                if dist is not None:
                    if esta_calibrado(floor.calibration):
                        extra = (
                            f", a unos {formatear_longitud(dist, units)} del router"
                        )
                    else:
                        extra = ", relativamente lejos del router en el plano"
            frags.append(
                f"Existe una zona con señal deficiente en «{ev.habitacion.nombre}»{extra}."
            )
        else:
            nombres = ", ".join(e.habitacion.nombre for e in deficientes)
            frags.append(f"Existen zonas con señal deficiente en: {nombres}.")
        recomendaciones.append(
            "Se recomienda instalar un punto de acceso adicional o recolocar el existente "
            "para mejorar las zonas con señal deficiente."
        )
    elif aceptables and not excelentes and not buenas:
        nombres = ", ".join(e.habitacion.nombre for e in aceptables)
        frags.append(
            f"La cobertura es solo aceptable en: {nombres}. "
            "Conviene revisar la ubicación del router o añadir un repetidor."
        )
        recomendaciones.append(
            "Valore recolocar el router hacia una zona más central o añadir un repetidor "
            "en las habitaciones con cobertura aceptable."
        )
    elif excelentes or buenas:
        ok = excelentes + buenas
        if len(ok) == len(evals):
            frags.append(
                "Todas las habitaciones evaluadas presentan cobertura buena o excelente."
            )
        else:
            nombres_ok = ", ".join(e.habitacion.nombre for e in ok)
            frags.append(f"La cobertura es buena o excelente en: {nombres_ok}.")

    return (" ".join(frags) if frags else None), recomendaciones


def _frase_router(
    dispositivos: list[DispositivoRed] | None,
    floor: NivelPlanta,
) -> str | None:
    gateway = None
    if dispositivos:
        gateway = next(
            (d for d in dispositivos if d.rol == RolDispositivo.GATEWAY),
            None,
        )
        if gateway is None:
            gateway = next(
                (d for d in dispositivos if d.tipo == TipoDispositivo.ROUTER),
                None,
            )

    ref = router_de_referencia(floor)
    if gateway and ref:
        nombre = gateway.hostname or gateway.ip
        return (
            f"El router de la red ({nombre}) está marcado en el plano como "
            f"«{ref.nombre}»; la cobertura se interpreta respecto a esa ubicación."
        )
    if gateway:
        nombre = gateway.hostname or gateway.ip
        return (
            f"Se ha identificado automáticamente el router de la red ({nombre}, gateway). "
            "Si lo coloca en el plano, el informe podrá relacionar las zonas débiles "
            "con su distancia al router."
        )
    if ref:
        return (
            f"La cobertura se analiza respecto al router marcado en el plano "
            f"(«{ref.nombre}»)."
        )
    return None


def generar_resumen_ejecutivo(
    session: SesionApp,
    networks: list[RedWifi],
    preferences: PreferenciasApp,
    analysis: ResultadoAnalisisCanales,
    *,
    stats_activa: EstadisticasCobertura | None = None,
    evals_activa: list[EvaluacionHabitacion] | None = None,
    dispositivos: list[DispositivoRed] | None = None,
) -> ResumenEjecutivo:
    """Construye párrafos legibles para un cliente no técnico."""
    resumen = ResumenEjecutivo()
    n = len(networks)
    if n == 0:
        resumen.parrafos.append("No se detectaron redes WiFi en el momento del informe.")
    elif n == 1:
        resumen.parrafos.append("Se detecta 1 red WiFi en el entorno.")
    else:
        resumen.parrafos.append(f"Se detectan {n} redes WiFi en el entorno.")

    frase_ch = _frase_canales(analysis)
    if frase_ch:
        resumen.parrafos.append(frase_ch)

    planta = session.planta_activa
    frase_router = _frase_router(dispositivos, planta)
    if frase_router:
        resumen.parrafos.append(frase_router)

    frase_cob = _frase_cobertura(stats_activa)
    if frase_cob:
        resumen.parrafos.append(frase_cob)

    evals = evals_activa or []
    frase_hab, recs = _frase_habitaciones(evals, planta, preferences.units)
    if frase_hab:
        resumen.parrafos.append(frase_hab)
    resumen.recomendaciones.extend(recs)

    if stats_activa and stats_activa.porcentaje_debil >= 25 and not resumen.recomendaciones:
        resumen.recomendaciones.append(
            "Hay una proporción relevante de zonas con señal débil. "
            "Se recomienda revisar la ubicación del router o instalar un punto de acceso adicional."
        )

    if not planta.measurements:
        resumen.parrafos.append(
            "Aún no hay mediciones de señal sobre el plano; el mapa de calor y el detalle "
            "por habitación aparecerán cuando se registren puntos de medida."
        )
    elif not evals and planta.habitaciones:
        resumen.parrafos.append(
            "Hay habitaciones dibujadas, pero no se pudo evaluar su cobertura con los datos actuales."
        )
    elif not planta.habitaciones and planta.measurements:
        resumen.recomendaciones.append(
            "Dibujar las habitaciones (Salón, Despacho…) permitirá un informe por zonas "
            "más fácil de entregar al cliente."
        )

    return resumen
