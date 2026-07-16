"""Escaneo ligero de puertos TCP para clasificación LAN."""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

PORTS_CLAVE = (80, 443, 554, 8008, 8009)


def escanear_puertos_ligeros(
    ips: list[str], *, timeout_ms: int = 400, max_workers: int = 32
) -> dict[str, list[int]]:
    timeout = max(0.1, timeout_ms / 1000.0)
    resultado: dict[str, list[int]] = {ip: [] for ip in ips}
    tareas = [(ip, p) for ip in ips for p in PORTS_CLAVE]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futuros = {pool.submit(_is_open, ip, p, timeout): (ip, p) for ip, p in tareas}
        for futuro in as_completed(futuros):
            ip, port = futuros[futuro]
            try:
                if futuro.result():
                    resultado[ip].append(port)
            except Exception:
                continue
    return resultado


def _is_open(ip: str, port: int, timeout: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((ip, port)) == 0
    finally:
        sock.close()

