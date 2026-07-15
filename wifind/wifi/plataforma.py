"""Fachada multiplataforma para escaneo y conexión WiFi."""

from __future__ import annotations

import sys

from wifind.wifi.red import RedWifi


def _obtener_backend():
    if sys.platform == "win32":
        from wifind.wifi import windows

        return windows
    if sys.platform == "darwin":
        from wifind.wifi import macos

        return macos
    from wifind.wifi import linux

    return linux


def requiere_contrasena(network: RedWifi) -> bool:
    """Indica si la red probablemente requiere contraseña."""
    return network.tipo_acceso() != "Abierta"


def es_red_empresarial(network: RedWifi) -> bool:
    return network.tipo_acceso() == "Empresarial"


def escanear_redes() -> list[RedWifi]:
    return _obtener_backend().escanear_redes()


def obtener_red_conectada() -> RedWifi | None:
    return _obtener_backend().obtener_red_conectada()


def conectar_a_red(
    network: RedWifi, password: str | None = None
) -> tuple[bool, str]:
    if not network.ssid or network.ssid == "(oculta)":
        return False, "No se puede conectar a una red oculta sin conocer su SSID."

    if es_red_empresarial(network):
        return False, (
            "Esta red parece empresarial (802.1X). "
            "Usa conectar_empresarial() con los parámetros EAP adecuados."
        )

    if requiere_contrasena(network) and not password:
        return False, "Esta red requiere contraseña."

    return _obtener_backend().conectar_a_red(network, password)


def conectar_empresarial(
    network: RedWifi,
    *,
    eap_method: str = "peap",
    identity: str,
    password: str | None = None,
    ca_cert_path: str | None = None,
    client_cert_path: str | None = None,
    client_cert_password: str | None = None,
) -> tuple[bool, str]:
    if not identity.strip():
        return False, "Se requiere identidad (usuario) para 802.1X."

    return _obtener_backend().conectar_empresarial(
        network,
        eap_method=eap_method,
        identity=identity,
        password=password,
        ca_cert_path=ca_cert_path,
        client_cert_path=client_cert_path,
        client_cert_password=client_cert_password,
    )


def desconectar_wifi() -> tuple[bool, str]:
    return _obtener_backend().desconectar_wifi()


def pista_error_escaneo() -> str:
    return _obtener_backend().pista_error_escaneo()


def pista_error_conexion() -> str:
    return _obtener_backend().pista_error_conexion()
