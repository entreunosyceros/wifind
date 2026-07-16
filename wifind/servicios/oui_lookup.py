"""Resolución local de fabricante por prefijo MAC (OUI)."""

from __future__ import annotations

from pathlib import Path

_OUI_BASE: dict[str, str] = {
    "44:48:B9": "ZTE",
    "8A:66:AF": "MAC aleatoria (privada)",
    "56:F6:12": "MAC aleatoria (privada)",
    "BC:FC:E7": "Samsung",
    "90:D0:92": "Xiaomi",
    "AC:E2:D3": "Huawei",
    "C0:BD:D1": "Xiaomi",
    "00:17:88": "Philips",
    "F4:F5:E8": "Google",
    "3C:5A:B4": "Google",
    "DC:A6:32": "Raspberry Pi",
    "18:B4:30": "Espressif",
}


def resolver_fabricante(mac: str) -> str:
    prefijo = _prefijo_oui(mac)
    if not prefijo:
        return ""
    extra = _cargar_oui_local().get(prefijo, "")
    if extra:
        return extra
    return _OUI_BASE.get(prefijo, "")


def _prefijo_oui(mac: str) -> str:
    if not mac:
        return ""
    partes = mac.upper().replace("-", ":").split(":")
    if len(partes) < 3:
        return ""
    return ":".join(partes[:3])


def _cargar_oui_local() -> dict[str, str]:
    path = Path.home() / ".config" / "wifind" / "oui.csv"
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            prefix, vendor = line.split(",", 1)
            pref = prefix.strip().upper().replace("-", ":")
            if len(pref) >= 8:
                data[pref[:8]] = vendor.strip()
    except OSError:
        return {}
    return data

