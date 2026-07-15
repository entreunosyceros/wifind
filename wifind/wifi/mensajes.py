"""Mensajes legibles para conexión WiFi (sin salida cruda de comandos)."""

from __future__ import annotations

import re

_RE_ANSI = re.compile(r"\x1b\[[0-9?;]*[a-zA-Z]")
_RE_PREFIJO_ERROR = re.compile(r"^(?:Error|Warning|Aviso)\s*:\s*", re.IGNORECASE)


def limpiar_salida_comando(texto: str) -> str:
    """Elimina códigos ANSI y normaliza espacios de la salida de un comando."""
    if not texto:
        return ""
    limpio = _RE_ANSI.sub("", texto)
    lineas = [ln.strip() for ln in limpio.splitlines() if ln.strip()]
    if not lineas:
        return ""
    mensaje = lineas[0]
    return _RE_PREFIJO_ERROR.sub("", mensaje).strip()


def mensaje_exito_conexion(ssid: str) -> str:
    nombre = ssid.strip() or "la red seleccionada"
    return f"Conectado correctamente a la red {nombre}."


def mensaje_exito_desconexion(ssid: str = "") -> str:
    nombre = ssid.strip()
    if nombre and nombre != "(oculta)":
        return f"Desconectado de la red {nombre}."
    return "Desconectado de la red WiFi."


def mensaje_error_conexion(salida: str, *, ssid: str = "") -> str:
    """Traduce errores habituales de nmcli/netsh a mensajes claros en español."""
    raw = limpiar_salida_comando(salida)
    if not raw:
        return "No se pudo conectar a la red."

    lower = raw.lower()
    nombre = ssid.strip()

    if "secrets were required" in lower or "no secrets" in lower:
        return "Esta red requiere contraseña."
    if any(
        p in lower
        for p in (
            "password",
            "contraseña",
            "psk",
            "802.1x authentication failed",
            "incorrect password",
            "clave",
        )
    ):
        return "Contraseña incorrecta o credenciales no válidas."
    if "no network with ssid" in lower or "no se encontró una red" in lower:
        if nombre:
            return f"No se encontró la red {nombre}. Vuelve a escanear e inténtalo de nuevo."
        return "No se encontró la red. Vuelve a escanear e inténtalo de nuevo."
    if "connection activation failed" in lower or "activación de la conexión" in lower:
        return "No se pudo activar la conexión. Comprueba la contraseña o la señal."
    if "timeout" in lower or ("tiempo" in lower and "agotado" in lower):
        return "Tiempo de espera agotado al conectar. Inténtalo de nuevo."
    if "permission denied" in lower or "not authorized" in lower or "no autorizado" in lower:
        return "No tienes permisos para gestionar conexiones WiFi en este equipo."
    if "device" in lower and "not ready" in lower:
        return "El adaptador WiFi no está listo. Espera unos segundos e inténtalo de nuevo."
    if "already" in lower and "connect" in lower:
        if nombre:
            return f"Ya estás conectado a la red {nombre}."
        return "Ya hay una conexión WiFi activa."

    # Evitar mostrar rutas D-Bus, UUIDs o salida técnica de NetworkManager.
    if _es_salida_tecnica(raw):
        return "No se pudo conectar a la red."

    return raw


def _es_salida_tecnica(texto: str) -> bool:
    if "/org/freedesktop/" in texto:
        return True
    if re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-", texto, re.IGNORECASE):
        return True
    if re.search(r"successfully activated|activado correctamente", texto, re.IGNORECASE):
        return True
    if re.search(r"^Device ['\"]|^Dispositivo ['«]", texto, re.IGNORECASE):
        return True
    return False
