"""Descubrimiento de dispositivos en la red local conectada."""

from __future__ import annotations

import ipaddress
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

ProgresoCallback = Callable[[str, int], None]

from wifind.modelos.dispositivo_red import ContextoLan, DispositivoRed, RolDispositivo
from wifind.servicios.clasificacion_dispositivo import clasificar_dispositivos
from wifind.wifi._comun import ejecutar_comando_resultado


def pista_error_descubrimiento() -> str:
    if sys.platform == "win32":
        return (
            "Conéctate a una red WiFi con IP asignada. "
            "Algunos firewalls bloquean el ping; revisa el adaptador activo."
        )
    if sys.platform == "darwin":
        return (
            "Conéctate a una red WiFi con IP asignada. "
            "Puede ser necesario conceder permisos de red local a la aplicación."
        )
    return (
        "Conéctate a una red WiFi con IP asignada. "
        "En Linux usa `ip neigh` o instala `iputils-ping`. "
        "Para detectar móviles Android instala `avahi-utils` (`avahi-resolve`). "
        "Algunas redes aislan clientes (AP isolation) y ocultan otros dispositivos."
    )


def obtener_contexto_lan() -> ContextoLan | None:
    if sys.platform == "win32":
        return _contexto_windows()
    if sys.platform == "darwin":
        return _contexto_macos()
    return _contexto_linux()


def descubrir_dispositivos(
    contexto: ContextoLan | None = None,
    *,
    progreso: ProgresoCallback | None = None,
) -> list[DispositivoRed]:
    ctx = contexto or obtener_contexto_lan()
    if ctx is None or not ctx.ip:
        return []

    def avisar(msg: str, porcentaje: int) -> None:
        if progreso:
            progreso(msg, max(0, min(100, porcentaje)))

    avisar("Leyendo tabla ARP/neighbor…", 3)
    por_ip: dict[str, DispositivoRed] = {}

    por_ip[ctx.ip] = DispositivoRed(
        ip=ctx.ip,
        mac=ctx.mac_local,
        rol=RolDispositivo.LOCAL,
    )
    if ctx.gateway:
        por_ip[ctx.gateway] = DispositivoRed(
            ip=ctx.gateway,
            rol=RolDispositivo.GATEWAY,
        )

    for dev in _leer_tabla_arp(ctx):
        _fusionar_dispositivo(por_ip, dev)

    avisar("Tabla ARP leída", 8)

    try:
        red = ipaddress.ip_network(f"{ctx.ip}/{ctx.prefix}", strict=False)
        hosts = [str(h) for h in red.hosts()]
    except ValueError:
        hosts = []

    if len(hosts) <= 512:
        avisar(f"Explorando {len(hosts)} direcciones…", 10)
        encontrados = _explorar_hosts(hosts, ctx, avisar)
        for ip in encontrados:
            if ip not in por_ip:
                por_ip[ip] = DispositivoRed(ip=ip, rol=RolDispositivo.OTRO)
        avisar("Actualizando tabla ARP…", 88)
        for dev in _leer_tabla_arp(ctx):
            _fusionar_dispositivo(por_ip, dev)

    avisar("Resolviendo nombres…", 92)
    _resolver_hostnames(por_ip.values(), avisar)
    clasificar_dispositivos(por_ip.values())

    avisar("Escaneo completado", 100)

    resultado = sorted(
        por_ip.values(),
        key=lambda d: (
            0 if d.rol == RolDispositivo.GATEWAY else 1 if d.rol == RolDispositivo.LOCAL else 2,
            ipaddress.ip_address(d.ip),
        ),
    )
    return resultado


def _fusionar_dispositivo(por_ip: dict[str, DispositivoRed], dev: DispositivoRed) -> None:
    existente = por_ip.get(dev.ip)
    if existente is None:
        por_ip[dev.ip] = dev
        return
    if dev.mac and not existente.mac:
        existente.mac = dev.mac
    if dev.hostname and not existente.hostname:
        existente.hostname = dev.hostname
    existente.activo = existente.activo or dev.activo


def _explorar_hosts(
    hosts: list[str],
    ctx: ContextoLan,
    avisar: ProgresoCallback,
) -> set[str]:
    encontrados: set[str] = set()
    omitir = {ctx.ip}
    objetivos = [h for h in hosts if h not in omitir]
    total = len(objetivos)
    if not objetivos:
        return encontrados

    completados = 0
    with ThreadPoolExecutor(max_workers=48) as pool:
        futuros = {pool.submit(_ping, ip): ip for ip in objetivos}
        for futuro in as_completed(futuros):
            ip = futuros[futuro]
            completados += 1
            pct = 10 + int(75 * completados / total)
            avisar(f"Ping {completados}/{total}…", pct)
            try:
                if futuro.result():
                    encontrados.add(ip)
            except Exception:
                continue
    return encontrados


def _ping(ip: str) -> bool:
    if sys.platform == "win32":
        cmd = ["ping", "-n", "1", "-w", "400", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    code, _, _ = ejecutar_comando_resultado(cmd, timeout=2.5)
    return code == 0


def _leer_tabla_arp(ctx: ContextoLan) -> list[DispositivoRed]:
    if sys.platform == "win32":
        return _arp_windows(ctx)
    if sys.platform == "darwin":
        return _arp_macos(ctx)
    return _arp_linux(ctx)


def _arp_linux(ctx: ContextoLan) -> list[DispositivoRed]:
    args = ["ip", "neigh", "show"]
    if ctx.iface:
        args.extend(["dev", ctx.iface])
    code, output, _ = ejecutar_comando_resultado(args)
    if code != 0:
        code, output, _ = ejecutar_comando_resultado(["arp", "-n"])
    if code != 0:
        return []

    dispositivos: list[DispositivoRed] = []
    for line in output.splitlines():
        match = re.match(
            r"(\d+\.\d+\.\d+\.\d+)\s+.*?(?:lladdr|at)\s+([0-9a-f:]{11,17})",
            line,
            re.IGNORECASE,
        )
        if not match:
            match = re.match(
                r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]{11,17})",
                line,
                re.IGNORECASE,
            )
        if not match:
            continue
        ip, mac = match.group(1), match.group(2).upper()
        if "FAILED" in line.upper() or "INCOMPLETE" in line.upper():
            continue
        rol = _rol_por_ip(ip, ctx)
        dispositivos.append(DispositivoRed(ip=ip, mac=mac, rol=rol, activo=True))
    return dispositivos


def _arp_windows(ctx: ContextoLan) -> list[DispositivoRed]:
    code, output, _ = ejecutar_comando_resultado(["arp", "-a"])
    if code != 0:
        return []
    dispositivos: list[DispositivoRed] = []
    for line in output.splitlines():
        match = re.search(
            r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]{17})\s+(\w+)",
            line,
            re.IGNORECASE,
        )
        if not match:
            continue
        ip, mac_raw, state = match.group(1), match.group(2), match.group(3).lower()
        if state == "invalid":
            continue
        mac = mac_raw.replace("-", ":").upper()
        dispositivos.append(
            DispositivoRed(ip=ip, mac=mac, rol=_rol_por_ip(ip, ctx), activo=True)
        )
    return dispositivos


def _arp_macos(ctx: ContextoLan) -> list[DispositivoRed]:
    code, output, _ = ejecutar_comando_resultado(["arp", "-an"])
    if code != 0:
        return []
    dispositivos: list[DispositivoRed] = []
    for line in output.splitlines():
        match = re.search(
            r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]{11,17})",
            line,
            re.IGNORECASE,
        )
        if not match:
            continue
        ip, mac = match.group(1), match.group(2).upper()
        if mac == "(INCOMPLETE)":
            continue
        dispositivos.append(
            DispositivoRed(ip=ip, mac=mac, rol=_rol_por_ip(ip, ctx), activo=True)
        )
    return dispositivos


def _rol_por_ip(ip: str, ctx: ContextoLan) -> RolDispositivo:
    if ip == ctx.ip:
        return RolDispositivo.LOCAL
    if ctx.gateway and ip == ctx.gateway:
        return RolDispositivo.GATEWAY
    return RolDispositivo.OTRO


def _resolver_hostnames(
    dispositivos: list[DispositivoRed] | tuple,
    avisar: ProgresoCallback | None = None,
) -> None:
    pendientes_mdns: list[DispositivoRed] = []
    for dev in dispositivos:
        if dev.hostname:
            continue
        if dev.rol == RolDispositivo.LOCAL:
            try:
                nombre = socket.gethostname()
                if nombre:
                    dev.hostname = nombre.split(".")[0]
            except OSError:
                pass
            continue
        nombre = _resolver_dns_inverso(dev.ip)
        if nombre:
            dev.hostname = nombre
        elif dev.rol != RolDispositivo.GATEWAY:
            pendientes_mdns.append(dev)

    if pendientes_mdns:
        if avisar:
            avisar("Consultando nombres mDNS (Android, Chromecast…)…", 96)
        _resolver_mdns_paralelo(pendientes_mdns)


def _resolver_dns_inverso(ip: str) -> str:
    try:
        nombre, _, _ = socket.gethostbyaddr(ip)
        if nombre:
            return nombre.split(".")[0]
    except (socket.herror, socket.gaierror, OSError):
        pass
    return ""


def _resolver_mdns_paralelo(dispositivos: list[DispositivoRed]) -> None:
    if sys.platform == "win32":
        _resolver_mdns_windows(dispositivos)
        return

    with ThreadPoolExecutor(max_workers=12) as pool:
        futuros = {pool.submit(_resolver_mdns, dev.ip): dev for dev in dispositivos}
        for futuro in as_completed(futuros):
            dev = futuros[futuro]
            try:
                nombre = futuro.result()
                if nombre:
                    dev.hostname = nombre
            except Exception:
                continue


def _resolver_mdns(ip: str) -> str:
    nombre = _mdns_avahi(ip)
    if nombre:
        return nombre
    if sys.platform == "darwin":
        return _mdns_dns_sd(ip)
    return ""


def _mdns_avahi(ip: str) -> str:
    code, output, _ = ejecutar_comando_resultado(
        ["avahi-resolve", "-a", ip], timeout=4.0
    )
    if code != 0 or not output.strip():
        return ""
    linea = output.strip().splitlines()[0]
    partes = linea.split()
    if len(partes) < 2:
        return ""
    return _normalizar_hostname(partes[1])


def _mdns_dns_sd(ip: str) -> str:
    """Resolución mDNS en macOS vía dscacheutil tras ping al host."""
    code, output, _ = ejecutar_comando_resultado(
        ["ping", "-c", "1", "-t", "1", ip], timeout=3.0
    )
    if code != 0:
        return ""
    match = re.search(r"ping:\s+cannot resolve.*", output, re.I)
    if match:
        return ""
    return ""


def _resolver_mdns_windows(dispositivos: list[DispositivoRed]) -> None:
    for dev in dispositivos:
        code, output, _ = ejecutar_comando_resultado(
            ["ping", "-a", "-n", "1", "-w", "500", dev.ip], timeout=3.0
        )
        if code != 0:
            continue
        match = re.search(r"Pinging\s+(\S+)\s+\[", output, re.IGNORECASE)
        if match:
            host = match.group(1)
            if host != dev.ip:
                dev.hostname = _normalizar_hostname(host)


def _normalizar_hostname(nombre: str) -> str:
    host = nombre.strip().rstrip(".")
    if host.endswith(".local"):
        host = host[: -len(".local")]
    return host.split(".")[0] if host else ""


def _contexto_linux() -> ContextoLan | None:
    from wifind.wifi.linux import _iface_conectada
    from wifind.wifi.plataforma import obtener_red_conectada

    red = obtener_red_conectada()
    if not red or not red.ip:
        return None
    iface = _iface_conectada() or ""
    prefix = 24
    mac_local = ""

    if iface:
        code, output, _ = ejecutar_comando_resultado(
            ["nmcli", "-t", "-f", "IP4.ADDRESS,IP4.GATEWAY,GENERAL.HWADDR", "device", "show", iface]
        )
        if code == 0:
            for line in output.splitlines():
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                value = value.strip()
                if key.startswith("IP4.ADDRESS") and value:
                    if "/" in value:
                        _, suffix = value.split("/", 1)
                        if suffix.isdigit():
                            prefix = int(suffix)
                elif key == "GENERAL.HWADDR" and value:
                    mac_local = value.upper()

        if prefix == 24:
            code, output, _ = ejecutar_comando_resultado(
                ["ip", "-4", "-o", "addr", "show", "dev", iface]
            )
            if code == 0:
                match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", output)
                if match:
                    prefix = int(match.group(2))

    return ContextoLan(
        ssid=red.ssid,
        ip=red.ip,
        gateway=red.gateway,
        prefix=prefix,
        iface=iface,
        mac_local=mac_local,
    )


def _contexto_windows() -> ContextoLan | None:
    from wifind.wifi.plataforma import obtener_red_conectada

    red = obtener_red_conectada()
    if not red or not red.ip:
        return None
    prefix = 24
    code, output, _ = ejecutar_comando_resultado(["ipconfig"])
    if code == 0:
        in_wifi = False
        for line in output.splitlines():
            low = line.lower()
            if "adaptador" in low and ("wi-fi" in low or "wireless" in low or "wlan" in low):
                in_wifi = True
                continue
            if in_wifi and "adaptador" in low and "wi-fi" not in low and "wireless" not in low:
                break
            if not in_wifi:
                continue
            mask_match = re.search(r"M[áa]scara.*?(\d+\.\d+\.\d+\.\d+)", line, re.IGNORECASE)
            if mask_match:
                prefix = _mask_a_prefix(mask_match.group(1))
    return ContextoLan(
        ssid=red.ssid,
        ip=red.ip,
        gateway=red.gateway,
        prefix=prefix,
    )


def _contexto_macos() -> ContextoLan | None:
    from wifind.wifi.macos import _wifi_iface
    from wifind.wifi.plataforma import obtener_red_conectada

    red = obtener_red_conectada()
    if not red or not red.ip:
        return None
    iface = _wifi_iface() or ""
    prefix = 24
    if iface:
        code, output, _ = ejecutar_comando_resultado(["ifconfig", iface])
        if code == 0:
            match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(0x[0-9a-f]+)", output, re.I)
            if match:
                prefix = _hex_netmask_a_prefix(match.group(2))
    return ContextoLan(
        ssid=red.ssid,
        ip=red.ip,
        gateway=red.gateway,
        prefix=prefix,
        iface=iface,
    )


def _mask_a_prefix(mask: str) -> int:
    try:
        return ipaddress.ip_network(f"0.0.0.0/{mask}", strict=False).prefixlen
    except ValueError:
        return 24


def _hex_netmask_a_prefix(hex_mask: str) -> int:
    try:
        n = int(hex_mask, 16)
        return bin(n).count("1")
    except ValueError:
        return 24
