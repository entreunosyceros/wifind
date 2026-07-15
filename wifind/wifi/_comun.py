"""Utilidades compartidas para backends WiFi."""

from __future__ import annotations

import re
import subprocess


def ejecutar_comando(args: list[str], timeout: float = 15.0) -> str:
    return ejecutar_comando_resultado(args, timeout)[1]


def ejecutar_comando_resultado(
    args: list[str], timeout: float = 15.0
) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return 127, "", "Comando no encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", "Tiempo de espera agotado"
    return result.returncode, result.stdout, result.stderr


def porcentaje_a_dbm(percent: int) -> int:
    clamped = max(0, min(100, percent))
    return int(round(clamped / 2 - 100))


def dbm_a_porcentaje(dbm: int) -> int:
    return max(0, min(100, int(round(2 * (dbm + 100)))))


def extraer_campo(text: str, pattern: str) -> str | None:
    for line in text.splitlines():
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def deduplicar_redes(networks: list) -> list:
    from wifind.wifi.red import RedWifi

    best: dict[tuple[str, str], RedWifi] = {}
    for net in networks:
        key = (net.ssid, net.bssid or net.ssid)
        existing = best.get(key)
        if existing is None:
            best[key] = net
            continue
        if net.signal_dbm > existing.signal_dbm:
            prefer = net
            other = existing
        else:
            prefer = existing
            other = net
        prefer.en_uso = prefer.en_uso or other.en_uso
        if not prefer.velocidad_anunciada:
            prefer.velocidad_anunciada = other.velocidad_anunciada
        if prefer.ancho_canal_mhz is None:
            prefer.ancho_canal_mhz = other.ancho_canal_mhz
        best[key] = prefer
    return sorted(best.values(), key=lambda n: n.signal_dbm, reverse=True)


def parsear_bitrate_mbps(texto: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*Mbit", texto or "", re.IGNORECASE)
    return float(match.group(1)) if match else None


def split_campos_nmcli(line: str) -> list[str]:
    """
    Divide una línea tabular de nmcli respetando ':' escapados (\\:) en valores.
    """
    campos: list[str] = []
    actual: list[str] = []
    i = 0
    while i < len(line):
        if line[i : i + 2] == "\\:":
            actual.append(":")
            i += 2
        elif line[i] == ":":
            campos.append("".join(actual))
            actual = []
            i += 1
        else:
            actual.append(line[i])
            i += 1
    campos.append("".join(actual))
    return campos


def parsear_entero(texto: str) -> int | None:
    match = re.search(r"-?\d+", texto.strip())
    return int(match.group(0)) if match else None
