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
from wifind.servicios.habitaciones import COLORES_NIVEL, evaluar_habitaciones_planta
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


def _rooms_section(evals) -> str:
    if not evals:
        return ""
    cards = "".join(
        f"""
        <div class="room-card" style="border-left-color:{COLORES_NIVEL.get(e.nivel, '#757575')}">
          <div class="room-name">{e.habitacion.nombre}</div>
          <div class="room-level" style="color:{COLORES_NIVEL.get(e.nivel, '#757575')}">{e.etiqueta}</div>
          <div class="room-meta">{"%.1f dBm" % e.media_dbm if e.media_dbm is not None else "Sin datos de señal"}</div>
        </div>
        """
        for e in evals
    )
    return f"""
    <section>
      <h2>Cobertura por habitación</h2>
      <div class="room-grid">{cards}</div>
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


def _summary_section(resumen) -> str:
    if not resumen.tiene_contenido:
        return ""
    paras = "".join(f"<p>{p}</p>" for p in resumen.parrafos)
    recs = ""
    if resumen.recomendaciones:
        items = "".join(f"<li>{r}</li>" for r in resumen.recomendaciones)
        recs = f"<h3>Recomendaciones</h3><ul class=\"recs\">{items}</ul>"
    return f"""
    <section class="executive">
      <h2>Resumen</h2>
      <div class="executive-body">{paras}{recs}</div>
    </section>
    """


def generar_informe_html(
    session: SesionApp,
    networks: list[RedWifi],
    preferences: PreferenciasApp,
    output_path: str | Path,
    *,
    logo_path: str | Path | None = None,
    dispositivos: list | None = None,
) -> Path:
    """
    Genera un informe HTML orientado a cliente: resumen narrativo,
    mapas, habitaciones y detalle técnico.
    """
    from wifind.servicios.narrativa_informe import (
        generar_resumen_ejecutivo,
        router_de_referencia,
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    channel_analysis = analizar_canales(networks)
    floor_sections: list[str] = []
    coverage_blocks: list[str] = []
    evals_activa: list = []
    active_stats = None

    for floor in session.floors:
        target_ssid = floor.target_ssids[0] if floor.target_ssids else ""
        points = [
            PuntoMedicion(x=m.x, y=m.y, signal_dbm=m.signal_dbm)
            for m in floor.measurements
        ]

        rooms_html = ""
        etiquetas_hab: dict[str, str] = {}
        evals: list = []
        stats = None
        if points:
            grid_x, grid_y, grid_z = interpolar_senal(
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
            if floor.habitaciones:
                evals = evaluar_habitaciones_planta(
                    floor, grid_x, grid_y, grid_z, preferences
                )
                etiquetas_hab = {e.habitacion.id: e.etiqueta for e in evals}
                rooms_html = _rooms_section(evals)

        if floor.id == session.planta_activa_id:
            active_stats = stats
            evals_activa = evals

        router = router_de_referencia(floor)
        radios = (5.0, 10.0, 15.0) if router else None

        figure = construir_figura_mapa_calor(
            points,
            target_ssid,
            x_max=floor.x_max,
            y_max=floor.y_max,
            floor_plan_path=floor.floor_plan_path,
            obstaculos=floor.obstaculos,
            access_points=floor.access_points,
            habitaciones=floor.habitaciones,
            etiquetas_habitacion=etiquetas_hab or None,
            router_referencia=router,
            radios_router_m=radios,
            calibracion=floor.calibration if router else None,
            unit_suffix=preferences.sufijo_longitud(),
            theme=preferences.theme,
        )
        map_b64 = _figure_to_base64_png(figure)

        floor_sections.append(
            f"""
            <section class="floor">
              <h2>Planta: {floor.name}</h2>
              <p>Medidas: {len(floor.measurements)} | Área: {floor.x_max} × {floor.y_max}</p>
              <img src="data:image/png;base64,{map_b64}" alt="Mapa {floor.name}" class="heatmap" />
              {rooms_html}
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

    coverage_detail = ""
    if active_stats is not None:
        coverage_detail = _coverage_section(
            active_stats.porcentaje_bueno,
            active_stats.porcentaje_debil,
            preferences.threshold_weak,
        )

    resumen = generar_resumen_ejecutivo(
        session,
        networks,
        preferences,
        channel_analysis,
        stats_activa=active_stats,
        evals_activa=evals_activa,
        dispositivos=dispositivos,
    )

    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    logo_tag = _logo_img_tag(Path(logo_path) if logo_path else None)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>{__app_name__} — Informe</title>
  <style>
    body {{ font-family: Georgia, "Times New Roman", serif; margin: 2rem auto; max-width: 900px; color: #222; line-height: 1.55; }}
    h1, h2, h3 {{ font-family: system-ui, sans-serif; color: #1565C0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-family: system-ui, sans-serif; font-size: 0.92rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #E3F2FD; }}
    .logo {{ max-height: 64px; }}
    .heatmap {{ max-width: 100%; border: 1px solid #ddd; margin: 1rem 0; }}
    .meta {{ color: #555; font-size: 0.95rem; font-family: system-ui, sans-serif; }}
    section {{ margin-bottom: 2rem; }}
    .executive {{
      background: #F5F9FF;
      border: 1px solid #BBDEFB;
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
    }}
    .executive-body p {{ margin: 0.65rem 0; font-size: 1.08rem; }}
    .recs {{ margin: 0.5rem 0 0 1.2rem; }}
    .room-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 0.75rem;
      margin-top: 0.75rem;
      font-family: system-ui, sans-serif;
    }}
    .room-card {{
      background: #f7f9fc;
      border: 1px solid #e0e0e0;
      border-left: 4px solid #1565C0;
      border-radius: 6px;
      padding: 0.75rem 1rem;
    }}
    .room-name {{ font-weight: 600; font-size: 1.05rem; }}
    .room-level {{ font-size: 1.15rem; font-weight: 700; margin-top: 0.25rem; }}
    .room-meta {{ color: #666; font-size: 0.85rem; margin-top: 0.2rem; }}
    details.technical {{ font-family: system-ui, sans-serif; margin-top: 2rem; }}
    details.technical summary {{ cursor: pointer; color: #1565C0; font-weight: 600; }}
  </style>
</head>
<body>
  <header>
    {logo_tag}
    <h1>Informe WiFi — {session.name}</h1>
    <p class="meta">Generado: {generated_at} | {__app_name__} v{__version__}</p>
  </header>

  {_summary_section(resumen)}

  {''.join(floor_sections)}

  <section>
    <h2>Intensidad en el dispositivo</h2>
    <img src="data:image/png;base64,{intensity_b64}" alt="Gráfico de intensidad" class="heatmap" />
  </section>

  <details class="technical" open>
    <summary>Detalle técnico</summary>
    {_networks_table(networks)}
    {_channel_section(channel_analysis)}
    {coverage_detail}
    {f'<section><h2>Resumen por planta</h2>{coverage_summary}</section>' if coverage_summary else ''}
  </details>
</body>
</html>
"""

    path.write_text(html, encoding="utf-8")
    return path
