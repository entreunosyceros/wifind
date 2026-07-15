"""Agrupación de puntos de acceso por SSID."""

from __future__ import annotations

from collections import Counter, defaultdict

from wifind.modelos.medicion import Medicion
from wifind.wifi.red import RedWifi


def agrupar_por_ssid(networks: list[RedWifi]) -> dict[str, list[RedWifi]]:
    """Agrupa redes detectadas por SSID, ordenadas por señal descendente."""
    grouped: dict[str, list[RedWifi]] = defaultdict(list)
    for network in networks:
        grouped[network.ssid].append(network)
    for ssid in grouped:
        grouped[ssid].sort(key=lambda n: n.signal_dbm, reverse=True)
    return dict(grouped)


def bssid_dominante_mediciones(
    measurements: list[Medicion],
) -> dict[str, str]:
    """
    Devuelve el BSSID más frecuente por SSID en las mediciones registradas.

    Las mediciones sin SSID o BSSID se omiten.
    """
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for measurement in measurements:
        if not measurement.ssid or not measurement.bssid:
            continue
        counters[measurement.ssid][measurement.bssid] += 1

    return {
        ssid: counter.most_common(1)[0][0]
        for ssid, counter in counters.items()
        if counter
    }
