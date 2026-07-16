"""Dispositivo detectado en la red local (LAN)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RolDispositivo(str, Enum):
    LOCAL = "local"
    GATEWAY = "gateway"
    OTRO = "otro"


class TipoDispositivo(str, Enum):
    ROUTER = "router"
    ESTE_EQUIPO = "este_equipo"
    PC = "pc"
    ANDROID = "android"
    TELEFONO = "telefono"
    TABLET = "tablet"
    CHROMECAST = "chromecast"
    CAMARA = "camara"
    IOT = "iot"
    DESCONOCIDO = "desconocido"


_ETIQUETAS_TIPO = {
    TipoDispositivo.ROUTER: "Router",
    TipoDispositivo.ESTE_EQUIPO: "Este equipo",
    TipoDispositivo.PC: "Ordenador",
    TipoDispositivo.ANDROID: "Android",
    TipoDispositivo.TELEFONO: "Teléfono",
    TipoDispositivo.TABLET: "Tablet",
    TipoDispositivo.CHROMECAST: "Chromecast",
    TipoDispositivo.CAMARA: "Cámara IP",
    TipoDispositivo.IOT: "IoT / Smart",
    TipoDispositivo.DESCONOCIDO: "Dispositivo",
}


@dataclass
class DispositivoRed:
    ip: str
    mac: str = ""
    hostname: str = ""
    rol: RolDispositivo = RolDispositivo.OTRO
    tipo: TipoDispositivo = TipoDispositivo.DESCONOCIDO
    fabricante: str = ""
    puertos_abiertos: list[int] = None
    activo: bool = True

    def __post_init__(self) -> None:
        if self.puertos_abiertos is None:
            self.puertos_abiertos = []
        if self.tipo == TipoDispositivo.DESCONOCIDO:
            if self.rol == RolDispositivo.GATEWAY:
                self.tipo = TipoDispositivo.ROUTER
            elif self.rol == RolDispositivo.LOCAL:
                self.tipo = TipoDispositivo.ESTE_EQUIPO

    @property
    def etiqueta(self) -> str:
        if self.hostname:
            return self.hostname
        return self.ip

    @property
    def tipo_legible(self) -> str:
        if self.rol == RolDispositivo.GATEWAY:
            return "Router (gateway)"
        if self.rol == RolDispositivo.LOCAL:
            return _ETIQUETAS_TIPO.get(self.tipo, "Este equipo")
        return _ETIQUETAS_TIPO.get(self.tipo, "Dispositivo")

    @property
    def etiqueta_rol(self) -> str:
        return self.tipo_legible

    @property
    def lineas_detalle(self) -> list[str]:
        """Líneas de detalle para tarjetas (nombre, IP, MAC)."""
        lineas: list[str] = []
        if self.hostname and self.hostname.lower() != "gateway":
            lineas.append(self.hostname)
        lineas.append(self.ip)
        if self.fabricante:
            lineas.append(self.fabricante)
        if self.mac:
            lineas.append(self.mac)
        return lineas

    def a_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "rol": self.rol.value,
            "tipo": self.tipo.value,
            "fabricante": self.fabricante,
            "puertos_abiertos": self.puertos_abiertos,
            "activo": self.activo,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> DispositivoRed:
        rol_raw = data.get("rol", "otro")
        try:
            rol = RolDispositivo(rol_raw)
        except ValueError:
            rol = RolDispositivo.OTRO
        tipo_raw = data.get("tipo", "desconocido")
        try:
            tipo = TipoDispositivo(tipo_raw)
        except ValueError:
            tipo = TipoDispositivo.DESCONOCIDO
        return cls(
            ip=data.get("ip", ""),
            mac=data.get("mac", ""),
            hostname=data.get("hostname", ""),
            rol=rol,
            tipo=tipo,
            fabricante=data.get("fabricante", ""),
            puertos_abiertos=list(data.get("puertos_abiertos", [])),
            activo=bool(data.get("activo", True)),
        )


@dataclass
class ContextoLan:
    ssid: str
    ip: str
    gateway: str
    prefix: int
    iface: str = ""
    mac_local: str = ""

    @property
    def red_cidr(self) -> str:
        return f"{self.ip}/{self.prefix}"
