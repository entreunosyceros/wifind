"""Almacenamiento local de contraseñas WiFi (solo en el equipo del usuario)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _ruta_credenciales() -> Path:
    base = Path.home() / ".config" / "wifind"
    base.mkdir(parents=True, exist_ok=True)
    return base / "wifi_credentials.json"


def _cargar() -> dict[str, str]:
    path = _ruta_credenciales()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        pass
    return {}


def _guardar(data: dict[str, str]) -> None:
    path = _ruta_credenciales()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def obtener_contrasena(ssid: str) -> str | None:
    if not ssid or ssid == "(oculta)":
        return None
    return _cargar().get(ssid)


def guardar_contrasena(ssid: str, password: str) -> None:
    if not ssid or ssid == "(oculta)" or not password:
        return
    data = _cargar()
    data[ssid] = password
    _guardar(data)


def eliminar_contrasena(ssid: str) -> None:
    if not ssid:
        return
    data = _cargar()
    if ssid in data:
        del data[ssid]
        _guardar(data)


def tiene_contrasena_guardada(ssid: str) -> bool:
    return bool(obtener_contrasena(ssid))
