"""Compatibilidad hacia atrás — usar wifind.wifi.plataforma."""

from wifind.wifi.red import RedWifi
from wifind.wifi.plataforma import (
    pista_error_conexion,
    conectar_a_red,
    obtener_red_conectada,
    es_red_empresarial,
    requiere_contrasena,
    pista_error_escaneo,
    escanear_redes,
)

__all__ = [
    "RedWifi",
    "pista_error_conexion",
    "conectar_a_red",
    "obtener_red_conectada",
    "es_red_empresarial",
    "requiere_contrasena",
    "pista_error_escaneo",
    "escanear_redes",
]
