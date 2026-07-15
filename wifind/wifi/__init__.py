"""Backends WiFi multiplataforma."""

from wifind.wifi.red import RedWifi
from wifind.wifi.plataforma import (
    conectar_empresarial,
    conectar_a_red,
    desconectar_wifi,
    es_red_empresarial,
    escanear_redes,
    obtener_red_conectada,
    pista_error_conexion,
    pista_error_escaneo,
    requiere_contrasena,
)

__all__ = [
    "RedWifi",
    "conectar_a_red",
    "conectar_empresarial",
    "desconectar_wifi",
    "es_red_empresarial",
    "escanear_redes",
    "obtener_red_conectada",
    "pista_error_conexion",
    "pista_error_escaneo",
    "requiere_contrasena",
]
