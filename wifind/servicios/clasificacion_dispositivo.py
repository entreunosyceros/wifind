"""Heurísticas para clasificar dispositivos LAN (teléfono, PC, router, IoT…)."""

from __future__ import annotations

import re

from wifind.modelos.dispositivo_red import DispositivoRed, RolDispositivo, TipoDispositivo

_PATRONES_ANDROID = (
    r"^android[_-]",
    r"android-\d",
    r"\.android",
)

_PATRONES_TELEFONO = (
    r"iphone",
    r"ipod",
    r"galaxy[\s-]?[s-z]\d",
    r"sm-[a-g]\d",
    r"sm-[a-g]\d\d",
    r"pixel",
    r"redmi",
    r"xiaomi",
    r"huawei",
    r"honor",
    r"oppo",
    r"vivo",
    r"oneplus",
    r"realme",
    r"poco",
    r"moto[\s-]?[gex]",
    r"mobile",
    r"phone",
    r"telefono",
    r"teléfono",
    r"celular",
)

_PATRONES_TABLET = (
    r"ipad",
    r"tablet",
    r"tab[\s-]?\d",
    r"galaxy[\s-]?tab",
    r"sm-t\d",
    r"kindle",
    r"fire[\s-]?hd",
)

_PATRONES_PC = (
    r"macbook",
    r"imac",
    r"macmini",
    r"mac[\s-]?pro",
    r"mac-",
    r"desktop",
    r"laptop",
    r"notebook",
    r"thinkpad",
    r"latitude",
    r"precision",
    r"optiplex",
    r"surface",
    r"workstation",
    r"pc-",
    r"win-",
    r"windows",
    r"ubuntu",
    r"fedora",
    r"debian",
    r"linux",
    r"server",
    r"servidor",
    r"nas-",
    r"synology",
    r"qnap",
    r"raspberry",
    r"rpi",
    r"nuc",
)

_PATRONES_ROUTER = (
    r"router",
    r"gateway",
    r"livebox",
    r"archer",
    r"deco",
    r"eero",
    r"orbi",
    r"mesh",
    r"repeater",
    r"extender",
    r"ap-",
    r"access[\s-]?point",
    r"openwrt",
    r"dd-wrt",
    r"asus-rt",
    r"rt-ax",
    r"rt-ac",
    r"fritz",
    r"movistar\.base",
)

_PATRONES_IOT = (
    r"esp32",
    r"esp8266",
    r"esp-",
    r"chromecast",
    r"google[\s-]?home",
    r"nest-",
    r"echo",
    r"alexa",
    r"hue",
    r"roku",
    r"appletv",
    r"apple[\s-]?tv",
    r"smart[\s-]?tv",
    r"lgwebos",
    r"samsungtv",
    r"tv-",
    r"tele",
    r"camera",
    r"cam-",
    r"ring-",
    r"shelly",
    r"sonoff",
    r"tuya",
    r"printer",
    r"impresora",
    r"hp-",
    r"canon",
    r"epson",
    r"brother",
    r"plug",
    r"bombilla",
    r"bulb",
    r"iot",
)

# Prefijos OUI → tipo (solo MACs no aleatorizadas).
_OUI_TIPOS: dict[str, TipoDispositivo] = {
    # IoT / embedded
    "24:6F:28": TipoDispositivo.IOT,
    "30:AE:A4": TipoDispositivo.IOT,
    "AC:67:B2": TipoDispositivo.IOT,
    "B4:E6:2D": TipoDispositivo.IOT,
    "C8:2B:96": TipoDispositivo.IOT,
    "DC:4F:22": TipoDispositivo.IOT,
    "18:B4:30": TipoDispositivo.IOT,
    # Virtual / PC
    "00:50:56": TipoDispositivo.PC,
    "00:0C:29": TipoDispositivo.PC,
    "08:00:27": TipoDispositivo.PC,
    "B8:27:EB": TipoDispositivo.PC,
    "DC:A6:32": TipoDispositivo.PC,
    "E4:5F:01": TipoDispositivo.PC,
    # Android / móviles (fabricantes habituales)
    "00:12:FB": TipoDispositivo.ANDROID,
    "00:15:99": TipoDispositivo.ANDROID,
    "00:16:32": TipoDispositivo.ANDROID,
    "00:46:4B": TipoDispositivo.ANDROID,
    "08:00:28": TipoDispositivo.ANDROID,
    "10:2C:6B": TipoDispositivo.ANDROID,
    "34:CE:00": TipoDispositivo.ANDROID,
    "44:48:B9": TipoDispositivo.ROUTER,
    "48:DB:50": TipoDispositivo.ANDROID,
    "54:60:09": TipoDispositivo.ANDROID,
    "64:CC:2E": TipoDispositivo.ANDROID,
    "78:11:DC": TipoDispositivo.ANDROID,
    "8C:F5:A3": TipoDispositivo.ANDROID,
    "90:D0:92": TipoDispositivo.ANDROID,
    "94:EB:2C": TipoDispositivo.ANDROID,
    "AC:E2:D3": TipoDispositivo.ANDROID,
    "BC:FC:E7": TipoDispositivo.TELEFONO,
    "C0:BD:D1": TipoDispositivo.ANDROID,
    "E0:DB:55": TipoDispositivo.ANDROID,
    "F4:F5:E8": TipoDispositivo.ANDROID,
}


def clasificar_dispositivo(dev: DispositivoRed) -> TipoDispositivo:
    if dev.rol == RolDispositivo.GATEWAY:
        return TipoDispositivo.ROUTER
    if dev.rol == RolDispositivo.LOCAL:
        return TipoDispositivo.ESTE_EQUIPO

    por_nombre = _clasificar_por_nombre(dev)
    if por_nombre is not None:
        return por_nombre

    por_puertos = _clasificar_por_puertos(dev.puertos_abiertos)
    if por_puertos is not None:
        return por_puertos

    por_mac = _clasificar_por_mac(dev.mac)
    if por_mac is not None:
        return por_mac

    return TipoDispositivo.DESCONOCIDO


def clasificar_dispositivos(dispositivos: list[DispositivoRed] | tuple) -> None:
    for dev in dispositivos:
        dev.tipo = clasificar_dispositivo(dev)


def _clasificar_por_nombre(dev: DispositivoRed) -> TipoDispositivo | None:
    texto = " ".join(filter(None, [dev.hostname, dev.ip])).lower()
    if not texto.strip():
        return None

    if _coincide(texto, _PATRONES_ROUTER):
        return TipoDispositivo.ROUTER
    if _coincide(texto, _PATRONES_ANDROID):
        return TipoDispositivo.ANDROID
    if _coincide(texto, _PATRONES_TELEFONO):
        return TipoDispositivo.TELEFONO
    if _coincide(texto, _PATRONES_TABLET):
        return TipoDispositivo.TABLET
    if _coincide(texto, _PATRONES_IOT):
        return TipoDispositivo.IOT
    if _coincide(texto, _PATRONES_PC):
        return TipoDispositivo.PC
    return None


def _clasificar_por_puertos(puertos: list[int]) -> TipoDispositivo | None:
    ports = set(puertos or [])
    if not ports:
        return None
    if 8008 in ports or 8009 in ports:
        return TipoDispositivo.CHROMECAST
    if 554 in ports:
        return TipoDispositivo.CAMARA
    if 80 in ports or 443 in ports:
        return TipoDispositivo.IOT
    return None


def _clasificar_por_mac(mac: str) -> TipoDispositivo | None:
    if not mac or _mac_es_aleatoria(mac):
        return None
    partes = mac.upper().replace("-", ":").split(":")
    if len(partes) < 3:
        return None
    prefijo = ":".join(partes[:3])
    return _OUI_TIPOS.get(prefijo)


def _mac_es_aleatoria(mac: str) -> bool:
    """MAC localmente administrada (p. ej. privacidad WiFi en Android/iOS)."""
    partes = mac.replace("-", ":").split(":")
    if not partes or not partes[0]:
        return False
    try:
        primer_byte = int(partes[0], 16)
    except ValueError:
        return False
    return bool(primer_byte & 0x02)


def _coincide(texto: str, patrones: tuple[str, ...]) -> bool:
    return any(re.search(p, texto, re.IGNORECASE) for p in patrones)
