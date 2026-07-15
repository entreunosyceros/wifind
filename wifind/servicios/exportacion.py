"""Exportación de figuras y datos tabulares."""

from __future__ import annotations

import csv
from pathlib import Path

from matplotlib.figure import Figure

from wifind.modelos.medicion import Medicion
from wifind.wifi.red import RedWifi


def exportar_figura_png(
    figure: Figure,
    output_path: str | Path,
    *,
    dpi: int = 150,
) -> Path:
    """Guarda una figura matplotlib como PNG."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format="png", dpi=dpi, bbox_inches="tight")
    return path


def exportar_figura_pdf(
    figure: Figure,
    output_path: str | Path,
) -> Path:
    """Guarda una figura matplotlib como PDF."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format="pdf", bbox_inches="tight")
    return path


def exportar_redes_csv(
    networks: list[RedWifi],
    output_path: str | Path,
) -> Path:
    """Exporta redes WiFi detectadas a CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "ssid",
        "bssid",
        "signal_dbm",
        "signal_percent",
        "channel",
        "band",
        "frequency_mhz",
        "security",
        "oculta",
        "cifrado_detallado",
        "tipo_radio",
        "velocidad_anunciada",
        "ancho_canal_mhz",
        "en_uso",
        "tx_bitrate_mbps",
        "rx_bitrate_mbps",
        "ip",
        "gateway",
        "dns",
        "timestamp",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for network in networks:
            writer.writerow(
                {
                    "ssid": network.ssid,
                    "bssid": network.bssid,
                    "signal_dbm": network.signal_dbm,
                    "signal_percent": network.signal_percent,
                    "channel": network.channel if network.channel is not None else "",
                    "band": network.band or "",
                    "frequency_mhz": (
                        network.frequency_mhz if network.frequency_mhz is not None else ""
                    ),
                    "security": network.security,
                    "oculta": network.oculta,
                    "cifrado_detallado": network.cifrado_detallado,
                    "tipo_radio": network.tipo_radio,
                    "velocidad_anunciada": network.velocidad_anunciada,
                    "ancho_canal_mhz": (
                        network.ancho_canal_mhz if network.ancho_canal_mhz is not None else ""
                    ),
                    "en_uso": network.en_uso,
                    "tx_bitrate_mbps": (
                        network.tx_bitrate_mbps if network.tx_bitrate_mbps is not None else ""
                    ),
                    "rx_bitrate_mbps": (
                        network.rx_bitrate_mbps if network.rx_bitrate_mbps is not None else ""
                    ),
                    "ip": network.ip,
                    "gateway": network.gateway,
                    "dns": network.dns,
                    "timestamp": network.timestamp if network.timestamp is not None else "",
                }
            )
    return path


def exportar_mediciones_csv(
    measurements: list[Medicion],
    output_path: str | Path,
) -> Path:
    """Exporta mediciones de señal a CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "x",
        "y",
        "signal_dbm",
        "ssid",
        "bssid",
        "timestamp",
        "floor_id",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for measurement in measurements:
            writer.writerow(measurement.a_dict())
    return path
