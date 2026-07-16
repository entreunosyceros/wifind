"""Backend WiFi para macOS (airport / networksetup)."""

from __future__ import annotations

import re
import time

from wifind.wifi._comun import (
    dbm_a_porcentaje,
    deduplicar_redes,
    extraer_campo,
    ejecutar_comando,
    ejecutar_comando_resultado,
)
from wifind.wifi.mensajes import (
    mensaje_error_conexion,
    mensaje_exito_conexion,
    mensaje_exito_desconexion,
)
from wifind.wifi.red import RedWifi, formatear_cifrado_detallado, inferir_tipo_radio

_AIRPORT = (
    "/System/Library/PrivateFrameworks/Apple80211.framework/"
    "Versions/Current/Resources/airport"
)


def escanear_redes() -> list[RedWifi]:
    output = ejecutar_comando([_AIRPORT, "-s"])
    if not output.strip():
        return []
    return _parse_airport_scan(output)


def obtener_red_conectada() -> RedWifi | None:
    output = ejecutar_comando([_AIRPORT, "-I"])
    ssid = extraer_campo(output, r"^\s*SSID:\s*(.+)$")
    bssid = extraer_campo(output, r"^\s*BSSID:\s*(.+)$")
    rssi = extraer_campo(output, r"^\s*(?:agrCtlRSSI|RSSI):\s*(-?\d+)")
    channel = extraer_campo(output, r"^\s*channel:\s*(\d+)")
    tx_rate = extraer_campo(output, r"^\s*lastTxRate:\s*(\d+)")
    max_rate = extraer_campo(output, r"^\s*maxRate:\s*(\d+)")
    if not ssid or not rssi:
        return None
    dbm = int(rssi)
    channel_num = int(channel) if channel and channel.isdigit() else None
    red = RedWifi(
        ssid=ssid.strip(),
        bssid=(bssid or "").strip().upper(),
        signal_dbm=dbm,
        signal_percent=dbm_a_porcentaje(dbm),
        channel=channel_num,
        security="Desconocida",
        en_uso=True,
        tx_bitrate_mbps=float(tx_rate) if tx_rate else None,
        rx_bitrate_mbps=float(max_rate) if max_rate else None,
        velocidad_anunciada=f"{max_rate} Mbit/s" if max_rate else "",
        tipo_radio=inferir_tipo_radio(velocidad_anunciada=max_rate or ""),
    )
    _enriquecer_ip_macos(red)
    return red


def _enriquecer_ip_macos(red: RedWifi) -> None:
    iface = _wifi_iface()
    if not iface:
        return
    output = ejecutar_comando(["ipconfig", "getifaddr", iface])
    if output.strip():
        red.ip = output.strip()
    route = ejecutar_comando(["netstat", "-nr"])
    for line in route.splitlines():
        if line.startswith("default") or line.startswith("0.0.0.0"):
            parts = line.split()
            if len(parts) >= 2:
                red.gateway = parts[1]
                break
    dns_out = ejecutar_comando(["scutil", "--dns"])
    dns_servers = re.findall(r"nameserver\[0\] : (\S+)", dns_out)
    if dns_servers:
        red.dns = ", ".join(dns_servers[:3])


def conectar_a_red(
    network: RedWifi, password: str | None = None
) -> tuple[bool, str]:
    if not network.ssid or network.ssid == "(oculta)":
        return False, "No se puede conectar a una red oculta sin conocer su SSID."

    iface = _wifi_iface()
    if not iface:
        return False, "No se encontró la interfaz WiFi."

    args = ["networksetup", "-setairportnetwork", iface, network.ssid]
    if password:
        args.append(password)

    code, out, err = ejecutar_comando_resultado(args, timeout=30.0)
    if code == 0:
        return True, mensaje_exito_conexion(network.ssid)
    return False, mensaje_error_conexion(f"{out}\n{err}", ssid=network.ssid)


def desconectar_wifi() -> tuple[bool, str]:
    red = obtener_red_conectada()
    if not red:
        return False, "No hay conexión WiFi activa."
    iface = _wifi_iface()

    # Intento 1: airport -z (puede no existir o estar restringido en algunas versiones).
    code, out, err = ejecutar_comando_resultado([_AIRPORT, "-z"], timeout=10.0)
    if code == 0:
        return True, mensaje_exito_desconexion(red.ssid)

    # Intento 2 (fallback): apagar/encender el WiFi con networksetup.
    # En macOS reciente suele estar menos restringido que la herramienta privada airport.
    if iface:
        ejecutar_comando_resultado(
            ["networksetup", "-setairportpower", iface, "off"], timeout=10.0
        )
        time.sleep(1.0)
        code2, _out2, _err2 = ejecutar_comando_resultado(
            ["networksetup", "-setairportpower", iface, "on"], timeout=10.0
        )
        if code2 == 0:
            return True, mensaje_exito_desconexion(red.ssid)

    return (
        False,
        "No se pudo desconectar la WiFi automáticamente en macOS. "
        "Prueba a desconectar manualmente desde Ajustes → Wi-Fi.",
    )


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
    _ = (eap_method, identity, password, ca_cert_path, client_cert_path, client_cert_password)
    return False, (
        "Las redes empresariales (802.1X) en macOS deben configurarse desde "
        "Preferencias del Sistema → Red → WiFi → Avanzado, o con un perfil "
        "de configuración (.mobileconfig). "
        f"Red: «{network.ssid}»."
    )


def pista_error_escaneo() -> str:
    return (
        "Comprueba que el WiFi esté activo. En macOS el comando airport puede "
        "requerir permisos de ubicación o ejecutarse desde Terminal."
    )


def pista_error_conexion() -> str:
    return (
        "En macOS usa Preferencias del Sistema → Red para redes empresariales "
        "o concede permisos a Terminal para gestionar WiFi."
    )


def _wifi_iface() -> str | None:
    output = ejecutar_comando(["networksetup", "-listallhardwareports"])
    blocks = re.split(r"\n\n+", output.strip())
    for block in blocks:
        if "Wi-Fi" in block or "AirPort" in block:
            match = re.search(r"Device:\s*(\S+)", block)
            if match:
                return match.group(1)
    return None


def _parse_airport_scan(output: str) -> list[RedWifi]:
    networks: list[RedWifi] = []
    lines = output.splitlines()
    if len(lines) < 2:
        return []

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        match = re.match(
            r"^(?P<ssid>.+?)\s+"
            r"(?P<bssid>[0-9a-f:]{17})\s+"
            r"(?P<rssi>-?\d+)\s+"
            r"(?P<channel>\d+)\s+"
            r"(?P<ht>[YN])\s+"
            r"(?P<cc>\S+)\s+"
            r"(?P<security>.+)$",
            line,
            re.IGNORECASE,
        )
        if not match:
            continue
        dbm = int(match.group("rssi"))
        channel_num = int(match.group("channel"))
        ht = match.group("ht").upper() == "Y"
        security = match.group("security").strip()
        networks.append(
            RedWifi(
                ssid=match.group("ssid").strip(),
                bssid=match.group("bssid").upper(),
                signal_dbm=dbm,
                signal_percent=dbm_a_porcentaje(dbm),
                channel=channel_num,
                security=security,
                cifrado_detallado=formatear_cifrado_detallado(security),
                tipo_radio=inferir_tipo_radio(ht=ht),
            )
        )

    return deduplicar_redes(networks)
