"""Backend WiFi para Windows (netsh)."""

from __future__ import annotations

import re
import tempfile
import xml.sax.saxutils as xml_escape
from pathlib import Path

from wifind.wifi._comun import (
    deduplicar_redes,
    extraer_campo,
    porcentaje_a_dbm,
    ejecutar_comando,
    ejecutar_comando_resultado,
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
)

_EAP_TYPES = {"peap": "25", "ttls": "21", "tls": "13"}


def escanear_redes() -> list[RedWifi]:
    output = ejecutar_comando(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if not output.strip():
        output = ejecutar_comando(["netsh", "wlan", "show", "networks"])
    return _parse_netsh_scan(output)


def obtener_red_conectada() -> RedWifi | None:
    output = ejecutar_comando(["netsh", "wlan", "show", "interfaces"])
    ssid = extraer_campo(output, r"^\s*SSID\s*:\s*(.+)$")
    bssid = extraer_campo(output, r"^\s*BSSID\s*:\s*(.+)$")
    signal = extraer_campo(output, r"^\s*Signal\s*:\s*(\d+)\s*%")
    channel = extraer_campo(output, r"^\s*Channel\s*:\s*(\d+)")
    auth = extraer_campo(output, r"^\s*Authentication\s*:\s*(.+)$")
    cipher = extraer_campo(output, r"^\s*Cipher\s*:\s*(.+)$")
    radio = extraer_campo(output, r"^\s*Radio type\s*:\s*(.+)$")
    rx_rate = extraer_campo(output, r"^\s*Receive rate \(Mbps\)\s*:\s*(\d+(?:\.\d+)?)")
    tx_rate = extraer_campo(output, r"^\s*Transmit rate \(Mbps\)\s*:\s*(\d+(?:\.\d+)?)")
    if not ssid or not signal:
        return None
    percent = int(signal)
    channel_num = int(channel) if channel and channel.isdigit() else None
    sec = (auth or "Desconocida").strip()
    red = RedWifi(
        ssid=ssid.strip(),
        bssid=(bssid or "").strip().upper(),
        signal_dbm=porcentaje_a_dbm(percent),
        signal_percent=percent,
        channel=channel_num,
        security=sec,
        cifrado_detallado=formatear_cifrado_detallado(sec, cipher=cipher or ""),
        tipo_radio=(radio or inferir_tipo_radio()).strip(),
        en_uso=True,
        tx_bitrate_mbps=float(tx_rate) if tx_rate else None,
        rx_bitrate_mbps=float(rx_rate) if rx_rate else None,
    )
    _enriquecer_ip_windows(red)
    return red


def _enriquecer_ip_windows(red: RedWifi) -> None:
    code, out, _ = ejecutar_comando_resultado(["ipconfig"])
    if code != 0:
        return
    current_adapter = False
    dns: list[str] = []
    for line in out.splitlines():
        if "Wireless" in line or "Wi-Fi" in line or "WLAN" in line:
            current_adapter = True
            continue
        if current_adapter and line and not line.startswith(" "):
            if "adapter" in line.lower() and "wireless" not in line.lower() and "wi-fi" not in line.lower():
                break
        if not current_adapter:
            continue
        ip_match = re.match(r"\s*IPv4.*?:\s*([\d.]+)", line, re.IGNORECASE)
        gw_match = re.match(r"\s*(?:Default Gateway|Puerta de enlace).*?:\s*([\d.]+)", line, re.IGNORECASE)
        dns_match = re.match(r"\s*(?:DNS Servers|Servidores DNS).*?:\s*([\d.]+)", line, re.IGNORECASE)
        if ip_match and not red.ip:
            red.ip = ip_match.group(1)
        if gw_match and red.gateway in ("", "0.0.0.0"):
            red.gateway = gw_match.group(1)
        if dns_match:
            dns.append(dns_match.group(1))
    if dns:
        red.dns = ", ".join(dns)


def conectar_a_red(
    network: RedWifi, password: str | None = None
) -> tuple[bool, str]:
    if not network.ssid or network.ssid == "(oculta)":
        return False, "No se puede conectar a una red oculta sin conocer su SSID."

    ssid = network.ssid
    if _profile_exists(ssid):
        code, out, err = ejecutar_comando_resultado(["netsh", "wlan", "connect", f"name={ssid}"])
        if code == 0:
            return True, mensaje_exito_conexion(ssid)
        return False, mensaje_error_conexion(f"{out}\n{err}", ssid=ssid)

    profile_path = _create_psk_profile(ssid, network.security, password)
    if profile_path is None:
        return False, "No se pudo crear el perfil de red para Windows."

    try:
        code, out, err = ejecutar_comando_resultado(
            ["netsh", "wlan", "add", "profile", f"filename={profile_path}"]
        )
        if code != 0:
            return False, mensaje_error_conexion(
                f"{out}\n{err}", ssid=ssid
            ) or "No se pudo guardar el perfil WiFi."

        code, out, err = ejecutar_comando_resultado(["netsh", "wlan", "connect", f"name={ssid}"])
        if code == 0:
            return True, mensaje_exito_conexion(ssid)
        return False, mensaje_error_conexion(f"{out}\n{err}", ssid=ssid)
    finally:
        Path(profile_path).unlink(missing_ok=True)


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
    if method not in _EAP_TYPES:
        return False, f"Método EAP no soportado: {eap_method}. Usa PEAP, TTLS o TLS."

    if method in {"peap", "ttls"} and not password:
        return False, "PEAP y TTLS requieren contraseña."
    if method == "tls" and not client_cert_path:
        return False, "TLS requiere certificado de cliente."

    ssid = network.ssid
    if _profile_exists(ssid):
        _set_enterprise_credentials(ssid, identity, password)
        code, out, err = ejecutar_comando_resultado(["netsh", "wlan", "connect", f"name={ssid}"])
        if code == 0:
            return True, mensaje_exito_conexion(ssid)
        return False, mensaje_error_conexion(f"{out}\n{err}", ssid=ssid)

    if method == "tls" and client_cert_path:
        imported = _import_client_cert(client_cert_path, client_cert_password)
        if not imported:
            return False, "No se pudo importar el certificado de cliente."

    profile_path = _create_enterprise_profile(
        ssid=ssid,
        eap_method=method,
        identity=identity,
        password=password,
        ca_cert_path=ca_cert_path,
        client_cert_path=client_cert_path,
    )
    if profile_path is None:
        return False, "No se pudo crear el perfil empresarial para Windows."

    try:
        code, out, err = ejecutar_comando_resultado(
            ["netsh", "wlan", "add", "profile", f"filename={profile_path}"]
        )
        if code != 0:
            return False, mensaje_error_conexion(
                f"{out}\n{err}", ssid=ssid
            ) or "No se pudo guardar el perfil WiFi."

        if method in {"peap", "ttls"}:
            _set_enterprise_credentials(ssid, identity, password)

        code, out, err = ejecutar_comando_resultado(["netsh", "wlan", "connect", f"name={ssid}"])
        if code == 0:
            return True, mensaje_exito_conexion(ssid)
        return False, mensaje_error_conexion(f"{out}\n{err}", ssid=ssid)
    finally:
        Path(profile_path).unlink(missing_ok=True)


def desconectar_wifi() -> tuple[bool, str]:
    red = obtener_red_conectada()
    if not red:
        return False, "No hay conexión WiFi activa."
    code, out, err = ejecutar_comando_resultado(["netsh", "wlan", "disconnect"])
    if code == 0:
        return True, mensaje_exito_desconexion(red.ssid)
    return False, mensaje_error_conexion(f"{out}\n{err}", ssid=red.ssid)


def pista_error_escaneo() -> str:
    return (
        "Comprueba que el adaptador WiFi esté activo y que el servicio "
        "WLAN esté en ejecución."
    )


def pista_error_conexion() -> str:
    return (
        "En Windows puede ser necesario ejecutar WiFind como administrador "
        "o crear el perfil de red previamente desde Configuración."
    )


def _parse_netsh_scan(output: str) -> list[RedWifi]:
    networks: list[RedWifi] = []
    current_ssid = ""
    current_bssid = ""
    current_auth = "Desconocida"
    current_cipher = ""
    current_radio = ""
    current_channel: int | None = None
    ssid_hidden = False

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        ssid_match = re.match(r"SSID\s+\d+\s*:\s*(.*)", line, re.IGNORECASE)
        if ssid_match:
            current_ssid = ssid_match.group(1).strip()
            ssid_hidden = current_ssid.lower() in ("", "hidden")
            current_bssid = ""
            current_auth = "Desconocida"
            current_cipher = ""
            current_radio = ""
            current_channel = None
            continue

        auth_match = re.match(r"Authentication\s*:\s*(.*)", line, re.IGNORECASE)
        if auth_match:
            current_auth = auth_match.group(1).strip()
            continue

        cipher_match = re.match(r"Cipher\s*:\s*(.*)", line, re.IGNORECASE)
        if cipher_match:
            current_cipher = cipher_match.group(1).strip()
            continue

        radio_match = re.match(r"Radio type\s*:\s*(.*)", line, re.IGNORECASE)
        if radio_match:
            current_radio = radio_match.group(1).strip()
            continue

        channel_match = re.match(r"Channel\s*:\s*(\d+)", line, re.IGNORECASE)
        if channel_match:
            current_channel = int(channel_match.group(1))
            continue

        bssid_match = re.match(
            r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:]{17})", line, re.IGNORECASE
        )
        if bssid_match and (current_ssid or ssid_hidden):
            current_bssid = bssid_match.group(1).upper()
            continue

        signal_match = re.match(r"Signal\s*:\s*(\d+)\s*%", line, re.IGNORECASE)
        if signal_match and (current_ssid or ssid_hidden):
            percent = int(signal_match.group(1))
            sec = current_auth
            networks.append(
                RedWifi(
                    ssid=current_ssid or "(oculta)",
                    bssid=current_bssid,
                    signal_dbm=porcentaje_a_dbm(percent),
                    signal_percent=percent,
                    channel=current_channel,
                    security=sec,
                    oculta=ssid_hidden,
                    cifrado_detallado=formatear_cifrado_detallado(sec, cipher=current_cipher),
                    tipo_radio=current_radio or inferir_tipo_radio(),
                )
            )

    return deduplicar_redes(networks)


def _profile_exists(ssid: str) -> bool:
    code, out, _ = ejecutar_comando_resultado(["netsh", "wlan", "show", "profiles"])
    if code != 0:
        return False
    target = ssid.strip().lower()
    for line in out.splitlines():
        match = re.match(
            r"\s*(?:All User Profile|Perfil de todos los usuarios)\s*:\s*(.+)",
            line,
            re.I,
        )
        if match and match.group(1).strip().lower() == target:
            return True
    return False


def _auth_encryption(security: str) -> tuple[str, str]:
    sec = security.lower()
    if "wpa3" in sec:
        return "WPA3SAE", "AES"
    if "wpa2" in sec:
        return "WPA2PSK", "AES"
    if "wpa" in sec:
        return "WPAPSK", "TKIP"
    if "wep" in sec:
        return "open", "WEP"
    return "open", "none"


def _create_psk_profile(
    ssid: str, security: str, password: str | None
) -> str | None:
    auth, encryption = _auth_encryption(security)
    safe_ssid = xml_escape.escape(ssid)
    safe_name = xml_escape.escape(ssid)

    if auth == "open" and encryption == "none":
        profile = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{safe_name}</name>
    <SSIDConfig>
        <SSID>
            <name>{safe_ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>open</authentication>
                <encryption>none</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
        </security>
    </MSM>
</WLANProfile>
"""
    else:
        if not password:
            return None
        safe_password = xml_escape.escape(password)
        profile = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{safe_name}</name>
    <SSIDConfig>
        <SSID>
            <name>{safe_ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>{auth}</authentication>
                <encryption>{encryption}</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{safe_password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>
"""

    return _write_temp_profile(profile)


def _create_enterprise_profile(
    *,
    ssid: str,
    eap_method: str,
    identity: str,
    password: str | None,
    ca_cert_path: str | None,
    client_cert_path: str | None,
) -> str | None:
    safe_ssid = xml_escape.escape(ssid)
    safe_name = xml_escape.escape(ssid)
    eap_config = _build_eap_config(
        eap_method=eap_method,
        identity=identity,
        password=password,
        ca_cert_path=ca_cert_path,
        client_cert_path=client_cert_path,
    )
    if eap_config is None:
        return None

    profile = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{safe_name}</name>
    <SSIDConfig>
        <SSID>
            <name>{safe_ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2</authentication>
                <encryption>AES</encryption>
                <useOneX>true</useOneX>
            </authEncryption>
            <OneX xmlns="http://www.microsoft.com/networking/OneX/v1">
                <cacheUserData>true</cacheUserData>
                <authMode>user</authMode>
                <EAPConfig>{eap_config}</EAPConfig>
            </OneX>
        </security>
    </MSM>
</WLANProfile>
"""
    return _write_temp_profile(profile)


def _build_eap_config(
    *,
    eap_method: str,
    identity: str,
    password: str | None,
    ca_cert_path: str | None,
    client_cert_path: str | None,
) -> str | None:
    thumbprint = _cert_thumbprint(ca_cert_path) if ca_cert_path else None
    peap_extensions = ""
    if eap_method in {"peap", "ttls"}:
        validation = "true" if thumbprint else "false"
        trusted_root = (
            f"<TrustedRootCA>{thumbprint}</TrustedRootCA>" if thumbprint else ""
        )
        peap_extensions = f"""
        <PeapExtensions>
          <PerformServerValidation>{validation}</PerformServerValidation>
          <AcceptServerName>false</AcceptServerName>
          {trusted_root}
        </PeapExtensions>"""

    if eap_method == "peap":
        safe_identity = xml_escape.escape(identity)
        safe_password = xml_escape.escape(password or "")
        return f"""<EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig" xmlns:eapCommon="http://www.microsoft.com/provisioning/EapCommon">
  <EapMethod>
    <Type xmlns="http://www.microsoft.com/provisioning/EapHostConfig">25</Type>
    <VendorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorId>
    <VendorType xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorType>
    <AuthorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</AuthorId>
  </EapMethod>
  <Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
    <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionProperties/V1">
      <Type>25</Type>
      <EapType xmlns="http://www.microsoft.com/provisioning/MsPeapConnectionProperties/V1">
        <ServersidePeap>false</ServersidePeap>
        <FastReconnect>true</FastReconnect>
        <InnerEapOptional>false</InnerEapOptional>
        <EapType>26</EapType>
        <EnableQuarantineChecks>false</EnableQuarantineChecks>
        <RequireCryptoBinding>false</RequireCryptoBinding>{peap_extensions}
        <BaseEapConnectionProperties xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionProperties/V1">
          <EapType xmlns="http://www.microsoft.com/provisioning/MsChapV2ConnectionProperties/V1">
            <UseWinLogonCredentials>false</UseWinLogonCredentials>
            <UserName>{safe_identity}</UserName>
            <Password>{safe_password}</Password>
          </EapType>
        </BaseEapConnectionProperties>
      </EapType>
    </Eap>
  </Config>
</EapHostConfig>"""

    if eap_method == "ttls":
        safe_identity = xml_escape.escape(identity)
        safe_password = xml_escape.escape(password or "")
        return f"""<EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig" xmlns:eapCommon="http://www.microsoft.com/provisioning/EapCommon">
  <EapMethod>
    <Type xmlns="http://www.microsoft.com/provisioning/EapHostConfig">21</Type>
    <VendorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorId>
    <VendorType xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorType>
    <AuthorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</AuthorId>
  </EapMethod>
  <Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
    <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionProperties/V1">
      <Type>21</Type>
      <EapType xmlns="http://www.microsoft.com/provisioning/EapTtlsConnectionProperties/V1">
        <ServerValidation>
          <DisableUserPromptForServerValidation>{str(not thumbprint).lower()}</DisableUserPromptForServerValidation>
          <ServerNames></ServerNames>
          {f"<TrustedRootCA>{thumbprint}</TrustedRootCA>" if thumbprint else ""}
        </ServerValidation>
        <Phase2Authentication>
          <EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig" xmlns:eapCommon="http://www.microsoft.com/provisioning/EapCommon">
            <EapMethod>
              <Type xmlns="http://www.microsoft.com/provisioning/EapHostConfig">26</Type>
              <VendorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorId>
              <VendorType xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorType>
              <AuthorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</AuthorId>
            </EapMethod>
            <Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
              <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionProperties/V1">
                <Type>26</Type>
                <EapType xmlns="http://www.microsoft.com/provisioning/MsChapV2ConnectionProperties/V1">
                  <UseWinLogonCredentials>false</UseWinLogonCredentials>
                  <UserName>{safe_identity}</UserName>
                  <Password>{safe_password}</Password>
                </EapType>
              </Eap>
            </Config>
          </EapHostConfig>
        </Phase2Authentication>
        <Phase1Identity>{safe_identity}</Phase1Identity>
      </EapType>
    </Eap>
  </Config>
</EapHostConfig>"""

    if eap_method == "tls":
        return f"""<EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig" xmlns:eapCommon="http://www.microsoft.com/provisioning/EapCommon">
  <EapMethod>
    <Type xmlns="http://www.microsoft.com/provisioning/EapHostConfig">13</Type>
    <VendorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorId>
    <VendorType xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</VendorType>
    <AuthorId xmlns="http://www.microsoft.com/provisioning/EapHostConfig">0</AuthorId>
  </EapMethod>
  <Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
    <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionProperties/V1">
      <Type>13</Type>
      <EapType xmlns="http://www.microsoft.com/provisioning/EapTlsConnectionProperties/V1">
        <CredentialsSource>
          <CertificateStore>
            <SimpleCertSelection>true</SimpleCertSelection>
          </CertificateStore>
        </CredentialsSource>
        <ServerValidation>
          <DisableUserPromptForServerValidation>{str(not thumbprint).lower()}</DisableUserPromptForServerValidation>
          <ServerNames></ServerNames>
          {f"<TrustedRootCA>{thumbprint}</TrustedRootCA>" if thumbprint else ""}
        </ServerValidation>
        <DifferentUsername>false</DifferentUsername>
        <PerformServerValidation>{str(bool(thumbprint)).lower()}</PerformServerValidation>
        <AcceptServerName>false</AcceptServerName>
      </EapType>
    </Eap>
  </Config>
</EapHostConfig>"""

    return None


def _write_temp_profile(profile: str) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(profile)
            return handle.name
    except OSError:
        return None


def _set_enterprise_credentials(
    ssid: str, identity: str, password: str | None
) -> None:
    args = [
        "netsh",
        "wlan",
        "set",
        "profileparameter",
        f"name={ssid}",
        f"userName={identity}",
    ]
    if password:
        args.append(f"password={password}")
    ejecutar_comando_resultado(args)


def _cert_thumbprint(cert_path: str) -> str | None:
    code, out, _ = ejecutar_comando_resultado(["certutil", "-dump", cert_path])
    if code != 0:
        return None
    match = re.search(r"Cert Hash\(sha1\):\s*([0-9a-f]+)", out, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _import_client_cert(cert_path: str, password: str | None) -> bool:
    args = ["certutil", "-user", "-importpfx", cert_path]
    if password:
        args.extend(["-p", password])
    code, _, _ = ejecutar_comando_resultado(args)
    return code == 0
