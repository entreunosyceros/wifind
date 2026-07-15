"""Generación de informes HTML resumidos."""

from __future__ import annotations

import base64
import datetime as dt
import io
from pathlib import Path

from wifind import __app_name__, __version__
from wifind.mapa_calor import PuntoMedicion, construir_figura_mapa_calor, construir_figura_intensidad, interpolar_senal
from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import SesionApp
from wifind.servicios.analisis_canales import ResultadoAnalisisCanales, analizar_canales
from wifind.servicios.cobertura import calcular_estadisticas_cobertura
from wifind.wifi.red import RedWifi

_LOGO_PATH = Path(__file__).resolve().parent.parent / "img" / "logo.png"


def _figure_to_base64_png(figure) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    from matplotlib import pyplot as plt

    plt.close(figure)
    return encoded


def _logo_img_tag(logo_path: Path | None = None) -> str:
    path = logo_path or _LOGO_PATH
    if path.is_file():
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'<img src="data:{mime};base64,{data}" alt="{__app_name__}" class="logo" />'
    return f'<h1 class="logo-text">{__app_name__}</h1>'


def _channel_section(analysis: ResultadoAnalisisCanales) -> str:
    rows = "".join(
        f"<tr><td>{row.channel}</td><td>{row.band}</td>"
        f"<td>{row.ap_count}</td><td>{row.saturation}</td></tr>"
        for row in analysis.tabla_saturacion
    )
    if not rows:
        rows = '<tr><td colspan="4">Sin datos de canales</td></tr>'

    rec_24 = analysis.canal_recomendado_24ghz if analysis.canal_recomendado_24ghz is not None else "—"
    rec_5 = analysis.canal_recomendado_5ghz if analysis.canal_recomendado_5ghz is not None else "—"
    return f"""
    <section>
      <h2>Análisis de canales</h2>
      <p>Canal recomendado 2.4 GHz: <strong>{rec_24}</strong> |
         Canal recomendado 5 GHz: <strong>{rec_5}</strong></p>
      <table>
        <thead><tr><th>Canal</th><th>Banda</th><th>APs</th><th>Saturación</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """


def _networks_table(networks: list[RedWifi], limit: int = 15) -> str:
    rows = "".join(
        f"<tr><td>{'●' if n.en_uso else ''}</td><td>{n.ssid}</td><td>{n.bssid}</td>"
        f"<td>{n.signal_dbm}</td><td>{n.channel or '—'}</td><td>{n.band or '—'}</td>"
        f"<td>{n.cifrado_detallado or n.security}</td><td>{n.tipo_radio or '—'}</td>"
        f"<td>{n.velocidad_anunciada or '—'}</td></tr>"
        for n in networks[:limit]
    )
    if not rows:
        rows = '<tr><td colspan="9">Sin redes detectadas</td></tr>'
    return f"""
    <section>
      <h2>Redes detectadas (top {limit})</h2>
      <table>
        <thead><tr><th>En uso</th><th>SSID</th><th>BSSID</th><th>Señal (dBm)</th>
        <th>Canal</th><th>Banda</th><th>Cifrado</th><th>Radio</th><th>Rate</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """


def _coverage_section(porcentaje_bueno: float, porcentaje_debil: float, threshold: int) -> str:
    return f"""
    <section>
      <h2>Cobertura</h2>
      <p>Umbral débil: <strong>{threshold} dBm</strong></p>
      <ul>
        <li>Cobertura buena: <strong>{porcentaje_bueno:.1f}%</strong></li>
        <li>Zonas débiles: <strong>{porcentaje_debil:.1f}%</strong></li>
      </ul>
    </section>
    """


def generar_informe_html(
    session: SesionApp,
    networks: list[RedWifi],
    preferences: PreferenciasApp,
    output_path: str | Path,
    *,
    logo_path: str | Path | None = None,
) -> Path:
    """
    Genera un informe HTML con mapas embebidos, análisis de canales y cobertura.

    Usa plantilla HTML simple sin dependencias externas de templating.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    channel_analysis = analizar_canales(networks)
    floor_sections: list[str] = []
    coverage_blocks: list[str] = []

    for floor in session.floors:
        target_ssid = floor.target_ssids[0] if floor.target_ssids else ""
        points = [
            PuntoMedicion(x=m.x, y=m.y, signal_dbm=m.signal_dbm)
            for m in floor.measurements
        ]
        figure = construir_figura_mapa_calor(
            points,
            target_ssid,
            x_max=floor.x_max,
            y_max=floor.y_max,
            floor_plan_path=floor.floor_plan_path,
            obstaculos=floor.obstaculos,
        )
        map_b64 = _figure_to_base64_png(figure)

        if points:
            _, _, grid_z = interpolar_senal(
                points,
                x_max=floor.x_max,
                y_max=floor.y_max,
                obstaculos=floor.obstaculos or None,
            )
            stats = calcular_estadisticas_cobertura(
                grid_z,
                floor.x_max,
                floor.y_max,
                preferences.threshold_weak,
            )
            coverage_blocks.append(
                f"<li><strong>{floor.name}</strong>: {stats.porcentaje_bueno:.1f}% buena, "
                f"{stats.porcentaje_debil:.1f}% débil</li>"
            )

        floor_sections.append(
            f"""
            <section class="floor">
              <h2>Planta: {floor.name}</h2>
              <p>Medidas: {len(floor.measurements)} | Área: {floor.x_max} × {floor.y_max} m</p>
              <img src="data:image/png;base64,{map_b64}" alt="Mapa {floor.name}" class="heatmap" />
            </section>
            """
        )

    intensity = session.intensity
    intensity_fig = construir_figura_intensidad(
        intensity.timestamps,
        intensity.values_dbm,
        intensity.ssid,
    )
    intensity_b64 = _figure_to_base64_png(intensity_fig)

    coverage_summary = ""
    if coverage_blocks:
        coverage_summary = "<ul>" + "".join(coverage_blocks) + "</ul>"

    planta_activa = session.planta_activa
    active_stats = None
    if planta_activa.measurements:
        pts = [
            PuntoMedicion(x=m.x, y=m.y, signal_dbm=m.signal_dbm)
            for m in planta_activa.measurements
        ]
        _, _, grid_z = interpolar_senal(
            pts,
            x_max=planta_activa.x_max,
            y_max=planta_activa.y_max,
            obstaculos=planta_activa.obstaculos or None,
        )
        active_stats = calcular_estadisticas_cobertura(
            grid_z,
            planta_activa.x_max,
            planta_activa.y_max,
            preferences.threshold_weak,
        )

    coverage_detail = ""
    if active_stats is not None:
        coverage_detail = _coverage_section(
            active_stats.porcentaje_bueno,
            active_stats.porcentaje_debil,
            preferences.threshold_weak,
        )

    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    logo_tag = _logo_img_tag(Path(logo_path) if logo_path else None)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>{__app_name__} — Informe</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #222; }}
    h1, h2 {{ color: #1565C0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #E3F2FD; }}
    .logo {{ max-height: 64px; }}
    .heatmap {{ max-width: 100%; border: 1px solid #ddd; margin: 1rem 0; }}
    .meta {{ color: #555; font-size: 0.95rem; }}
    section {{ margin-bottom: 2rem; }}
  </style>
</head>
<body>
  <header>
    {logo_tag}
    <h1>Informe WiFi — {session.name}</h1>
    <p class="meta">Generado: {generated_at} | {__app_name__} v{__version__}</p>
  </header>

  {_networks_table(networks)}
  {_channel_section(channel_analysis)}
  {coverage_detail}
  {f'<section><h2>Resumen por planta</h2>{coverage_summary}</section>' if coverage_summary else ''}

  <section>
    <h2>Intensidad en el dispositivo</h2>
    <img src="data:image/png;base64,{intensity_b64}" alt="Gráfico de intensidad" class="heatmap" />
  </section>

  {''.join(floor_sections)}
</body>
</html>
"""

    path.write_text(html, encoding="utf-8")
    return path
