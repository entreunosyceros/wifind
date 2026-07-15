"""Red WiFi detectada."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


def canal_a_banda(channel: int | None) -> str | None:
    if channel is None:
        return None
    if 1 <= channel <= 14:
        return "2.4 GHz"
    if channel >= 36:
        return "5 GHz"
    return None


def parsear_ancho_canal(texto: str) -> int | None:
    """Convierte '20 MHz', '80MHz', etc. a entero."""
    match = re.search(r"(\d+)\s*MHz", texto or "", re.IGNORECASE)
    return int(match.group(1)) if match else None


def formatear_cifrado_detallado(
    security: str = "",
    wpa_flags: str = "",
    rsn_flags: str = "",
    cipher: str = "",
) -> str:
    """Resume cifrado a partir de flags de nmcli/netsh."""
    flags = f"{wpa_flags} {rsn_flags} {security} {cipher}".lower()
    partes: list[str] = []

    if "wpa3" in flags or "sae" in flags:
        partes.append("WPA3")
    elif "wpa2" in flags:
        partes.append("WPA2")
    elif "wpa" in flags:
        partes.append("WPA")

    if "802.1x" in flags or "enterprise" in flags or "eap" in flags:
        partes.append("802.1X")
    elif "psk" in flags or "wpa" in flags:
        if "802.1X" not in partes:
            partes.append("PSK")

    if "ccmp" in flags or "aes" in flags:
        partes.append("AES-CCMP")
    elif "gcmp" in flags:
        partes.append("GCMP")
    if "tkip" in flags:
        partes.append("TKIP")

    if "open" in flags and not partes:
        return "Abierta"
    if not partes:
        sec = (security or "").strip()
        return sec if sec and sec not in ("--", "(ninguno)") else "Desconocida"
    return " + ".join(dict.fromkeys(partes))


def inferir_tipo_radio(
    *,
    band: str | None = None,
    frequency_mhz: int | None = None,
    ancho_canal_mhz: int | None = None,
    velocidad_anunciada: str = "",
    ht: bool = False,
    vht: bool = False,
    he: bool = False,
    radio_type: str = "",
) -> str:
    """Estima el estándar 802.11 a partir de capacidades disponibles."""
    if radio_type.strip():
        return radio_type.strip()

    if he:
        return "802.11ax"
    if vht:
        return "802.11ac"
    if ht:
        return "802.11n"

    if ancho_canal_mhz and ancho_canal_mhz >= 80:
        return "802.11ac"
    if ancho_canal_mhz and ancho_canal_mhz >= 40:
        return "802.11n"

    rate_match = re.search(r"(\d+(?:\.\d+)?)", velocidad_anunciada or "")
    if rate_match:
        rate = float(rate_match.group(1))
        if rate > 54:
            return "802.11n"

    freq = frequency_mhz
    if freq is None and band:
        freq = 2400 if "2.4" in band else 5000 if "5" in band else None

    if freq and freq >= 5000:
        return "802.11a/ac"
    if freq and freq < 3000:
        return "802.11g/n"
    return "802.11"


def nivel_barras_senal(signal_dbm: int, thresholds: dict[str, int] | None = None) -> int:
    """Devuelve 0–4 rayas según intensidad en dBm."""
    t = thresholds or {"excellent": -50, "good": -60, "fair": -70, "weak": -80}
    if signal_dbm >= t["excellent"]:
        return 4
    if signal_dbm >= t["good"]:
        return 3
    if signal_dbm >= t["fair"]:
        return 2
    if signal_dbm >= t.get("weak", -80):
        return 1
    return 0


@dataclass
class RedWifi:
    ssid: str
    bssid: str
    signal_dbm: int
    signal_percent: int
    channel: int | None
    security: str
    band: str | None = None
    frequency_mhz: int | None = None
    timestamp: float | None = field(default_factory=time.time)
    oculta: bool = False
    cifrado_detallado: str = ""
    tipo_radio: str = ""
    velocidad_anunciada: str = ""
    ancho_canal_mhz: int | None = None
    en_uso: bool = False
    tx_bitrate_mbps: float | None = None
    rx_bitrate_mbps: float | None = None
    ip: str = ""
    gateway: str = ""
    dns: str = ""

    def __post_init__(self) -> None:
        if not self.ssid.strip():
            self.oculta = True
            if not self.ssid:
                self.ssid = "(oculta)"
        if self.band is None and self.channel is not None:
            self.band = canal_a_banda(self.channel)
        if not self.cifrado_detallado:
            self.cifrado_detallado = formatear_cifrado_detallado(self.security)
        if not self.tipo_radio:
            self.tipo_radio = inferir_tipo_radio(
                band=self.band,
                frequency_mhz=self.frequency_mhz,
                ancho_canal_mhz=self.ancho_canal_mhz,
                velocidad_anunciada=self.velocidad_anunciada,
            )

    def calidad_senal(self, thresholds: dict[str, int] | None = None) -> str:
        t = thresholds or {"excellent": -50, "good": -60, "fair": -70}
        if self.signal_dbm >= t["excellent"]:
            return "Excelente"
        if self.signal_dbm >= t["good"]:
            return "Buena"
        if self.signal_dbm >= t["fair"]:
            return "Regular"
        return "Débil"

    def nivel_barras_senal(self, thresholds: dict[str, int] | None = None) -> int:
        return nivel_barras_senal(self.signal_dbm, thresholds)

    def es_abierta(self) -> bool:
        """True si la red no requiere contraseña (WPA/WEP/802.1X)."""
        flags = f"{self.cifrado_detallado} {self.security}".lower()
        if any(x in flags for x in ("802.1x", "enterprise", "eap")):
            return False
        cifrado = (self.cifrado_detallado or "").strip().lower()
        if cifrado == "abierta":
            return True
        if any(x in cifrado for x in ("wpa", "wep", "psk", "sae", "gcmp")):
            return False
        security = (self.security or "").strip().lower()
        if any(x in security for x in ("wpa", "wep", "802.1x", "enterprise")):
            return False
        if not security or security in ("desconocida", "unknown", "--", "none", "open"):
            return True
        return "open" in security

    def tipo_acceso(self) -> str:
        """Clasificación visible: Abierta, Con contraseña o Empresarial."""
        flags = f"{self.cifrado_detallado} {self.security}".lower()
        if any(x in flags for x in ("802.1x", "enterprise", "eap")):
            return "Empresarial"
        if self.es_abierta():
            return "Abierta"
        return "Con contraseña"

    def a_dict(self) -> dict:
        return {
            "ssid": self.ssid,
            "bssid": self.bssid,
            "signal_dbm": self.signal_dbm,
            "signal_percent": self.signal_percent,
            "channel": self.channel,
            "security": self.security,
            "band": self.band,
            "frequency_mhz": self.frequency_mhz,
            "timestamp": self.timestamp,
            "oculta": self.oculta,
            "cifrado_detallado": self.cifrado_detallado,
            "tipo_radio": self.tipo_radio,
            "velocidad_anunciada": self.velocidad_anunciada,
            "ancho_canal_mhz": self.ancho_canal_mhz,
            "en_uso": self.en_uso,
            "tx_bitrate_mbps": self.tx_bitrate_mbps,
            "rx_bitrate_mbps": self.rx_bitrate_mbps,
            "ip": self.ip,
            "gateway": self.gateway,
            "dns": self.dns,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> RedWifi:
        return cls(
            ssid=data.get("ssid", "") or "(oculta)",
            bssid=data.get("bssid", ""),
            signal_dbm=int(data["signal_dbm"]),
            signal_percent=int(data["signal_percent"]),
            channel=data.get("channel"),
            security=data.get("security", "Desconocida"),
            band=data.get("band"),
            frequency_mhz=data.get("frequency_mhz"),
            timestamp=data.get("timestamp"),
            oculta=bool(data.get("oculta", False)),
            cifrado_detallado=data.get("cifrado_detallado", ""),
            tipo_radio=data.get("tipo_radio", ""),
            velocidad_anunciada=data.get("velocidad_anunciada", ""),
            ancho_canal_mhz=data.get("ancho_canal_mhz"),
            en_uso=bool(data.get("en_uso", False)),
            tx_bitrate_mbps=data.get("tx_bitrate_mbps"),
            rx_bitrate_mbps=data.get("rx_bitrate_mbps"),
            ip=data.get("ip", ""),
            gateway=data.get("gateway", ""),
            dns=data.get("dns", ""),
        )
