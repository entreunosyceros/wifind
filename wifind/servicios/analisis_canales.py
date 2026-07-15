"""Análisis de saturación y recomendación de canales WiFi."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from wifind.wifi.red import RedWifi, canal_a_banda

# Canales válidos por banda (simplificado para entornos habituales).
CHANNELS_24GHZ = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
CHANNELS_5GHZ = (
    36, 40, 44, 48,
    52, 56, 60, 64,
    100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
    149, 153, 157, 161, 165,
)


@dataclass
class FilaSaturacion:
    channel: int
    band: str
    ap_count: int
    saturation: str


@dataclass
class ResultadoAnalisisCanales:
    conteos_24ghz: dict[int, int] = field(default_factory=dict)
    conteos_5ghz: dict[int, int] = field(default_factory=dict)
    canal_recomendado_24ghz: int | None = None
    canal_recomendado_5ghz: int | None = None
    tabla_saturacion: list[FilaSaturacion] = field(default_factory=list)


def _saturation_label(ap_count: int) -> str:
    if ap_count == 0:
        return "Libre"
    if ap_count <= 2:
        return "Baja"
    if ap_count <= 5:
        return "Media"
    return "Alta"


def _recommended_channel(counts: dict[int, int], valid_channels: tuple[int, ...]) -> int | None:
    if not counts:
        return valid_channels[0] if valid_channels else None
    return min(valid_channels, key=lambda ch: (counts.get(ch, 0), ch))


def analizar_canales(networks: list[RedWifi]) -> ResultadoAnalisisCanales:
    """
    Analiza la distribución de APs por canal en 2.4 y 5 GHz.

    Devuelve conteos por banda, canal recomendado (menor saturación) y tabla
    de saturación por canal.
    """
    counts_24: Counter[int] = Counter()
    counts_5: Counter[int] = Counter()

    for network in networks:
        if network.channel is None:
            continue
        band = network.band or canal_a_banda(network.channel)
        if band == "2.4 GHz":
            counts_24[network.channel] += 1
        elif band == "5 GHz":
            counts_5[network.channel] += 1

    conteos_24ghz = {ch: counts_24.get(ch, 0) for ch in CHANNELS_24GHZ}
    conteos_5ghz = {ch: counts_5.get(ch, 0) for ch in CHANNELS_5GHZ}

    tabla_saturacion: list[FilaSaturacion] = []
    for channel, ap_count in sorted(conteos_24ghz.items()):
        if ap_count > 0:
            tabla_saturacion.append(
                FilaSaturacion(
                    channel=channel,
                    band="2.4 GHz",
                    ap_count=ap_count,
                    saturation=_saturation_label(ap_count),
                )
            )
    for channel, ap_count in sorted(conteos_5ghz.items()):
        if ap_count > 0:
            tabla_saturacion.append(
                FilaSaturacion(
                    channel=channel,
                    band="5 GHz",
                    ap_count=ap_count,
                    saturation=_saturation_label(ap_count),
                )
            )

    return ResultadoAnalisisCanales(
        conteos_24ghz=conteos_24ghz,
        conteos_5ghz=conteos_5ghz,
        canal_recomendado_24ghz=_recommended_channel(conteos_24ghz, CHANNELS_24GHZ),
        canal_recomendado_5ghz=_recommended_channel(conteos_5ghz, CHANNELS_5GHZ),
        tabla_saturacion=tabla_saturacion,
    )
