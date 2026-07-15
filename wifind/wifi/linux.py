"""Backend WiFi para Linux (nmcli / iw)."""

from __future__ import annotations

import re

from wifind.wifi._comun import (
    dbm_a_porcentaje,
    deduplicar_redes,
    parsear_bitrate_mbps,
    parsear_entero,
    porcentaje_a_dbm,
    ejecutar_comando,
    ejecutar_comando_resultado,
    split_campos_nmcli,
)
from wifind.wifi.mensajes import (
    mensaje_error_conexion,
    mensaje_exito_conexion,
    mensaje_exito_desconexion,
)
from wifind.wifi.red import (
    RedWifi,
    formatear_cifrado_detallado,
    inferir_tipo_radio,
    parsear_ancho_canal,
)

_EAP_METHODS = {"peap", "ttls", "tls"}


def escanear_redes() -> list[RedWifi]:
    networks = _scan_nmcli()
    if networks:
        return networks
    return _scan_iw()


def listar_interfaces_wifi() -> list[str]:
    """Interfaces WiFi gestionadas por NetworkManager."""
    code, output, _ = ejecutar_comando_resultado(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]
    )
    if code != 0 or not output.strip():
        return _interfaces_wifi_iw()

    ifaces: list[str] = []
    for line in output.splitlines():
        parts = split_campos_nmcli(line)
        if len(parts) < 2:
            continue
        device, dev_type = parts[0].strip(), parts[1].strip().lower()
        if dev_type == "wifi" and device:
            ifaces.append(device)
    return ifaces if ifaces else _interfaces_wifi_iw()


def _interfaces_wifi_iw() -> list[str]:
    output = ejecutar_comando(["iw", "dev"])
    if not output.strip():
        return []
    return re.findall(r"Interface\s+(\S+)", output)


def obtener_red_conectada() -> RedWifi | None:
    output = ejecutar_comando(
        [
            "nmcli",
            "-t",
            "-f",
            "ACTIVE,SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY,RATE,IN-USE,WPA-FLAGS,RSN-FLAGS,BANDWIDTH",
            "device",
            "wifi",
        ]
    )
    for line in output.splitlines():
        parts = split_campos_nmcli(line)
        if len(parts) < 6:
            continue
        active = parts[0]
        if active.strip().lower() not in ("yes", "sí", "si"):
            continue
        ssid = parts[1]
        bssid = parts[2]
        signal = parts[3]
        channel = parts[4]
        freq = parts[5] if len(parts) > 5 else ""
        security = parts[6] if len(parts) > 6 else ""
        rate = parts[7] if len(parts) > 7 else ""
        wpa = parts[9] if len(parts) > 9 else ""
        rsn = parts[10] if len(parts) > 10 else ""
        bandwidth = parts[11] if len(parts) > 11 else ""
        percent = parsear_entero(signal)
        if percent is None:
            continue
        channel_num = parsear_entero(channel)
        frequency_mhz = parsear_entero(freq)
        ancho = parsear_ancho_canal(bandwidth)
        sec = security.strip() or "Desconocida"
        red = RedWifi(
            ssid=ssid.strip() or "(oculta)",
            bssid=bssid.strip().upper(),
            signal_dbm=porcentaje_a_dbm(percent),
            signal_percent=percent,
            channel=channel_num,
            security=sec,
            frequency_mhz=frequency_mhz,
            oculta=not ssid.strip(),
            cifrado_detallado=formatear_cifrado_detallado(sec, wpa, rsn),
            velocidad_anunciada=rate.strip(),
            ancho_canal_mhz=ancho,
            en_uso=True,
            tipo_radio=inferir_tipo_radio(
                frequency_mhz=frequency_mhz,
                ancho_canal_mhz=ancho,
                velocidad_anunciada=rate,
            ),
        )
        iface = _iface_conectada()
        if iface:
            _enriquecer_conexion_linux(red, iface)
        return red
    return None


def _iface_conectada() -> str | None:
    code, output, _ = ejecutar_comando_resultado(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]
    )
    if code != 0:
        return _wifi_iface()
    for line in output.splitlines():
        parts = split_campos_nmcli(line)
        if len(parts) < 3:
            continue
        device, dev_type, state = parts[0].strip(), parts[1].strip().lower(), parts[2].strip().lower()
        if dev_type == "wifi" and "connected" in state:
            return device
    return _wifi_iface()


def _enriquecer_conexion_linux(red: RedWifi, iface: str) -> None:
    code, output, _ = ejecutar_comando_resultado(
        ["nmcli", "-t", "-f", "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS", "device", "show", iface]
    )
    if code == 0:
        dns_list: list[str] = []
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            value = value.strip()
            if key.startswith("IP4.ADDRESS") and value:
                red.ip = value.split("/")[0]
            elif key == "IP4.GATEWAY" and value:
                red.gateway = value
            elif key.startswith("IP4.DNS") and value:
                dns_list.append(value)
        if dns_list:
            red.dns = ", ".join(dns_list)

    link = ejecutar_comando(["iw", "dev", iface, "link"])
    if link.strip():
        tx = re.search(r"tx bitrate:\s*(\d+(?:\.\d+)?)", link, re.IGNORECASE)
        rx = re.search(r"rx bitrate:\s*(\d+(?:\.\d+)?)", link, re.IGNORECASE)
        if tx:
            red.tx_bitrate_mbps = float(tx.group(1))
        if rx:
            red.rx_bitrate_mbps = float(rx.group(1))


def conectar_a_red(
    network: RedWifi, password: str | None = None
) -> tuple[bool, str]:
    if not network.ssid or network.ssid == "(oculta)":
        return False, "No se puede conectar a una red oculta sin conocer su SSID."

    args = ["nmcli", "device", "wifi", "connect", network.ssid]
    if network.bssid:
        args.extend(["bssid", network.bssid])
    if password:
        args.extend(["password", password])

    code, out, err = ejecutar_comando_resultado(args, timeout=30.0)
    if code == 0:
        return True, mensaje_exito_conexion(network.ssid)
    if "nmcli" in err.lower() or code == 127:
        return False, (
            "NetworkManager (nmcli) no está disponible. "
            "Instálalo o conecta la red desde el sistema."
        )
    return False, mensaje_error_conexion(f"{out}\n{err}", ssid=network.ssid)


def desconectar_wifi() -> tuple[bool, str]:
    red = obtener_red_conectada()
    if not red:
        return False, "No hay conexión WiFi activa."
    iface = _iface_conectada()
    if not iface:
        return False, "No se encontró la interfaz WiFi conectada."
    code, out, err = ejecutar_comando_resultado(
        ["nmcli", "device", "disconnect", iface], timeout=15.0
    )
    if code == 0:
        return True, mensaje_exito_desconexion(red.ssid)
    if "nmcli" in err.lower() or code == 127:
        return False, (
            "NetworkManager (nmcli) no está disponible. "
            "Desconecta la red desde el gestor del sistema."
        )
    return False, mensaje_error_conexion(f"{out}\n{err}", ssid=red.ssid)


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
    if not network.ssid or network.ssid == "(oculta)":
        return False, "No se puede conectar a una red oculta sin conocer su SSID."

    method = eap_method.strip().lower()
    if method not in _EAP_METHODS:
        return False, f"Método EAP no soportado: {eap_method}. Usa PEAP, TTLS o TLS."

    if method in {"peap", "ttls"} and not password:
        return False, "PEAP y TTLS requieren contraseña."
    if method == "tls" and not client_cert_path:
        return False, "TLS requiere certificado de cliente."

    iface = _wifi_iface()
    con_name = f"wifind-{network.ssid}"

    args = [
        "nmcli",
        "connection",
        "add",
        "type",
        "wifi",
        "con-name",
        con_name,
        "ssid",
        network.ssid,
        "wifi-sec.key-mgmt",
        "wpa-eap",
        "802-1x.eap",
        method,
        "802-1x.identity",
        identity,
    ]
    if iface:
        args.extend(["ifname", iface])

    if method in {"peap", "ttls"}:
        args.extend(["802-1x.password", password or ""])
        args.extend(["802-1x.phase2-auth", "mschapv2"])

    if ca_cert_path:
        args.extend(["802-1x.ca-cert", ca_cert_path])

    if method == "tls":
        args.extend(["802-1x.client-cert", client_cert_path or ""])
        if client_cert_password:
            args.extend(["802-1x.private-key-password", client_cert_password])

    code, out, err = ejecutar_comando_resultado(args, timeout=30.0)
    if code != 0:
        return False, mensaje_error_conexion(f"{out}\n{err}", ssid=network.ssid) or (
            "No se pudo crear el perfil 802.1X."
        )

    up_args = ["nmcli", "connection", "up", con_name]
    if iface:
        up_args.extend(["ifname", iface])

    code, out, err = ejecutar_comando_resultado(up_args, timeout=30.0)
    if code == 0:
        return True, mensaje_exito_conexion(network.ssid)
    return False, mensaje_error_conexion(
        f"{out}\n{err}", ssid=network.ssid
    ) or "No se pudo activar la conexión empresarial."


def pista_error_escaneo() -> str:
    ifaces = listar_interfaces_wifi()
    if not ifaces:
        return (
            "No se detectó ninguna interfaz WiFi. Comprueba que la antena USB "
            "esté conectada y reconocida (ip link / nmcli device). "
            "Instala NetworkManager (nmcli) o el paquete 'iw'."
        )
    return (
        f"Interfaces WiFi detectadas: {', '.join(ifaces)}. "
        "Si no aparecen redes, activa la antena (rfkill unblock wifi) "
        "o ejecuta: nmcli device wifi rescan ifname <interfaz>."
    )


def pista_error_conexion() -> str:
    return (
        "En Linux comprueba que NetworkManager esté activo y que tu usuario "
        "tenga permisos para gestionar conexiones WiFi."
    )


def _scan_nmcli() -> list[RedWifi]:
    ifaces = listar_interfaces_wifi()
    targets = ifaces if ifaces else [None]
    networks: list[RedWifi] = []
    seen_ifaces: set[str | None] = set()

    for iface in targets:
        if iface in seen_ifaces:
            continue
        seen_ifaces.add(iface)

        rescan = ["nmcli", "device", "wifi", "rescan"]
        if iface:
            rescan.extend(["ifname", iface])
        ejecutar_comando(rescan, timeout=12.0)

        args = [
            "nmcli",
            "-t",
            "-f",
            "SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY,RATE,IN-USE,WPA-FLAGS,RSN-FLAGS,BANDWIDTH",
            "device",
            "wifi",
            "list",
        ]
        if iface:
            args.extend(["ifname", iface])
        output = ejecutar_comando(args)
        if output.strip():
            networks.extend(_parse_nmcli(output))

    return deduplicar_redes(networks) if networks else []


def _parse_nmcli(output: str) -> list[RedWifi]:
    networks: list[RedWifi] = []
    for line in output.splitlines():
        parts = split_campos_nmcli(line)
        if len(parts) < 5:
            continue
        raw_ssid, bssid, signal, channel = parts[:4]
        freq = parts[4] if len(parts) > 4 else ""
        security = parts[5] if len(parts) > 5 else "Desconocida"
        rate = parts[6] if len(parts) > 6 else ""
        in_use = parts[7] if len(parts) > 7 else ""
        wpa = parts[8] if len(parts) > 8 else ""
        rsn = parts[9] if len(parts) > 9 else ""
        bandwidth = parts[10] if len(parts) > 10 else ""
        oculta = not raw_ssid.strip()
        ssid = raw_ssid.strip() or "(oculta)"
        percent = parsear_entero(signal)
        if percent is None:
            continue
        channel_num = parsear_entero(channel)
        frequency_mhz = parsear_entero(freq)
        ancho = parsear_ancho_canal(bandwidth)
        sec = security.strip() or "Desconocida"
        networks.append(
            RedWifi(
                ssid=ssid,
                bssid=bssid.strip().upper(),
                signal_dbm=porcentaje_a_dbm(percent),
                signal_percent=percent,
                channel=channel_num,
                security=sec,
                frequency_mhz=frequency_mhz,
                oculta=oculta,
                cifrado_detallado=formatear_cifrado_detallado(sec, wpa, rsn),
                velocidad_anunciada=rate.strip(),
                ancho_canal_mhz=ancho,
                en_uso=in_use.strip() == "*",
                tipo_radio=inferir_tipo_radio(
                    frequency_mhz=frequency_mhz,
                    ancho_canal_mhz=ancho,
                    velocidad_anunciada=rate,
                ),
            )
        )
    return deduplicar_redes(networks)


def _scan_iw() -> list[RedWifi]:
    iface = _wifi_iface()
    if not iface:
        return []
    output = ejecutar_comando(["iw", "dev", iface, "scan"], timeout=20.0)
    if not output.strip():
        return []
    return _parse_iw(output)


def _wifi_iface() -> str | None:
    ifaces = listar_interfaces_wifi()
    if ifaces:
        return ifaces[0]
    output = ejecutar_comando(["iw", "dev"])
    match = re.search(r"Interface\s+(\S+)", output)
    return match.group(1) if match else None


def _parse_iw(output: str) -> list[RedWifi]:
    networks: list[RedWifi] = []
    blocks = re.split(r"(?=BSS )", output)
    for block in blocks:
        bssid_match = re.search(r"BSS ([0-9a-f:]+)", block, re.IGNORECASE)
        ssid_match = re.search(r"SSID: (.+)", block)
        signal_match = re.search(r"signal: (-?\d+(?:\.\d+)?) dBm", block)
        channel_match = re.search(r"primary channel: (\d+)", block)
        freq_match = re.search(r"freq: (\d+)", block)
        width_match = re.search(r"primary channel:\s*\d+\s*\((\d+)\s*MHz\)", block) or re.search(
            r"channel width:\s*(\d+)\s*MHz", block, re.IGNORECASE
        )
        ht = bool(re.search(r"HT capabilities", block))
        vht = bool(re.search(r"VHT capabilities", block))
        he = bool(re.search(r"HE capabilities", block))
        rsn = re.search(r"RSN:\s*(.+)", block)
        wpa = re.search(r"WPA:\s*(.+)", block)
        if not ssid_match or not signal_match:
            continue
        dbm = int(float(signal_match.group(1)))
        channel_num: int | None = None
        if channel_match:
            channel_num = int(channel_match.group(1))
        frequency_mhz: int | None = None
        if freq_match:
            frequency_mhz = int(freq_match.group(1))
        ancho = int(width_match.group(1)) if width_match else None
        ssid_raw = ssid_match.group(1).strip()
        sec = "Desconocida"
        if rsn or wpa:
            sec = "WPA/WPA2"
        networks.append(
            RedWifi(
                ssid=ssid_raw or "(oculta)",
                bssid=(bssid_match.group(1).upper() if bssid_match else ""),
                signal_dbm=dbm,
                signal_percent=dbm_a_porcentaje(dbm),
                channel=channel_num,
                security=sec,
                frequency_mhz=frequency_mhz,
                oculta=not ssid_raw,
                cifrado_detallado=formatear_cifrado_detallado(
                    sec,
                    wpa.group(1) if wpa else "",
                    rsn.group(1) if rsn else "",
                ),
                ancho_canal_mhz=ancho,
                tipo_radio=inferir_tipo_radio(
                    frequency_mhz=frequency_mhz,
                    ancho_canal_mhz=ancho,
                    ht=ht,
                    vht=vht,
                    he=he,
                ),
            )
        )
    return deduplicar_redes(networks)
