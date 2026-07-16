"""Diagrama de topología LAN (router + dispositivos conectados)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.text import Text
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from wifind.modelos.dispositivo_red import (
    DispositivoRed,
    RolDispositivo,
    TipoDispositivo,
    _ETIQUETAS_TIPO,
)
from wifind.ui.mpl_estilo import colores_tema


@dataclass
class _NodoArt:
    dev: DispositivoRed
    ancho: float
    alto: float
    caja: FancyBboxPatch
    textos: list[tuple[Text, float]] = field(default_factory=list)


class GraficoDispositivos(QWidget):
    """Mapa en estrella con nodos arrastrables y vista desplazable."""

    _RADIO_LAYOUT = 1.45
    _VIEW_SPAN_MIN = 3.8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._theme = "dark"
        self._ssid = ""
        self._dispositivos: list[DispositivoRed] = []
        self._posiciones: dict[str, tuple[float, float]] = {}
        self._nodos: dict[str, _NodoArt] = {}
        self._enlaces: list[FancyArrowPatch] = []
        self._hub_ip: str | None = None
        self._drag_ip: str | None = None
        self._drag_offset = (0.0, 0.0)
        self._panning = False
        self._pan_start: tuple[float, float] = (0.0, 0.0)
        self._pan_view_start: tuple[float, float] = (0.0, 0.0)
        self._pan_x = 0.0
        self._pan_y = 0.1
        self._view_span_y = self._VIEW_SPAN_MIN
        self._ajustar_vista_pendiente = False

        self._fig = Figure(figsize=(8, 5), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._fig.subplots_adjust(left=0.01, right=0.99, top=0.94, bottom=0.03)
        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._canvas.mpl_connect("button_release_event", self._on_release)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        dpi = self._fig.get_dpi()
        self._fig.set_size_inches(w / dpi, h / dpi, forward=True)
        if self._ajustar_vista_pendiente and self._dispositivos:
            self._ajustar_vista_a_contenido()
            self._ajustar_vista_pendiente = False
            self._renderizar()
        elif self._dispositivos:
            self._aplicar_vista()
        else:
            self._renderizar()

    def _aspecto_widget(self) -> float:
        return self.width() / max(self.height(), 1)

    def _limites_ejes(self) -> tuple[tuple[float, float], tuple[float, float]]:
        y_span = self._view_span_y
        x_span = y_span * self._aspecto_widget()
        return (
            (self._pan_x - x_span / 2, self._pan_x + x_span / 2),
            (self._pan_y - y_span / 2, self._pan_y + y_span / 2),
        )

    def _ajustar_vista_a_contenido(self) -> None:
        if not self._posiciones:
            self._pan_x = 0.0
            self._pan_y = 0.1
            self._view_span_y = self._VIEW_SPAN_MIN
            return

        pad = 0.75
        xs: list[float] = []
        ys: list[float] = []
        for ip, (x, y) in self._posiciones.items():
            nodo = self._nodos.get(ip)
            hw = (nodo.ancho / 2) if nodo else 0.5
            hh = (nodo.alto / 2) if nodo else 0.25
            xs.extend((x - hw, x + hw))
            ys.extend((y - hh, y + hh))

        x_min, x_max = min(xs) - pad, max(xs) + pad
        y_min, y_max = min(ys) - pad, max(ys) + pad
        self._pan_x = (x_min + x_max) / 2
        self._pan_y = (y_min + y_max) / 2
        content_y = max(y_max - y_min, self._VIEW_SPAN_MIN)
        content_x = max(x_max - x_min, self._VIEW_SPAN_MIN * self._aspecto_widget())
        self._view_span_y = max(content_y, content_x / max(self._aspecto_widget(), 0.5))

    def _aplicar_vista(self) -> None:
        xlim, ylim = self._limites_ejes()
        self._ax.set_xlim(*xlim)
        self._ax.set_ylim(*ylim)
        self._canvas.draw_idle()

    def actualizar(
        self,
        dispositivos: list[DispositivoRed],
        *,
        ssid: str = "",
        theme: str = "dark",
    ) -> None:
        self._theme = theme
        self._ssid = ssid
        self._dispositivos = list(dispositivos)

        ips_actuales = {d.ip for d in dispositivos if d.ip}
        self._posiciones = {ip: pos for ip, pos in self._posiciones.items() if ip in ips_actuales}

        nuevas = [d for d in dispositivos if d.ip and d.ip not in self._posiciones]
        if nuevas:
            self._posiciones.update(self._layout_inicial(dispositivos, nuevas))

        self._ajustar_vista_pendiente = bool(dispositivos)
        if self.width() > 100 and self.height() > 80:
            self._ajustar_vista_a_contenido()
            self._ajustar_vista_pendiente = False

        self._renderizar()

    def _layout_inicial(
        self,
        dispositivos: list[DispositivoRed],
        nuevos: list[DispositivoRed],
    ) -> dict[str, tuple[float, float]]:
        posiciones: dict[str, tuple[float, float]] = {}
        gateway = next((d for d in dispositivos if d.rol == RolDispositivo.GATEWAY), None)
        centro = self._posiciones.get(gateway.ip, (0.0, 0.2)) if gateway else (0.0, 0.2)
        radio = self._RADIO_LAYOUT

        for dev in nuevos:
            if dev.rol == RolDispositivo.GATEWAY:
                posiciones[dev.ip] = (0.0, 0.2)
            elif dev.rol == RolDispositivo.LOCAL:
                posiciones[dev.ip] = (0.0, -1.55)
            else:
                otros = [d for d in dispositivos if d.rol == RolDispositivo.OTRO]
                idx = otros.index(dev) if dev in otros else 0
                n = max(len(otros), 1)
                angulo = (2 * math.pi * idx / n) - math.pi / 2
                posiciones[dev.ip] = (
                    centro[0] + radio * math.cos(angulo),
                    centro[1] + radio * math.sin(angulo),
                )
        return posiciones

    def _renderizar(self) -> None:
        c = colores_tema(self._theme)
        self._fig.patch.set_facecolor(c["fig"])
        self._ax.clear()
        self._ax.set_facecolor(c["fig"])
        xlim, ylim = self._limites_ejes()
        self._ax.set_xlim(*xlim)
        self._ax.set_ylim(*ylim)
        self._ax.set_aspect("equal")
        self._ax.axis("off")
        self._nodos.clear()
        self._enlaces.clear()

        titulo = f"Dispositivos en «{self._ssid}»" if self._ssid else "Dispositivos en la red local"
        self._fig.suptitle(titulo, fontsize=12, color=c["text"], y=0.98)

        if not self._dispositivos:
            self._hub_ip = None
            self._ax.text(
                0.5,
                0.5,
                "Sin dispositivos detectados.\nConéctate a una red y pulsa «Escanear».",
                transform=self._ax.transAxes,
                ha="center",
                va="center",
                color=c["text_muted"],
                fontsize=11,
            )
            self._canvas.draw_idle()
            return

        gateway = next((d for d in self._dispositivos if d.rol == RolDispositivo.GATEWAY), None)
        if gateway and gateway.ip:
            self._hub_ip = gateway.ip
        elif self._dispositivos:
            self._hub_ip = self._dispositivos[0].ip
        else:
            self._hub_ip = None

        for dev in self._dispositivos:
            if not dev.ip:
                continue
            pos = self._posiciones.get(dev.ip)
            if pos is None:
                continue
            self._nodos[dev.ip] = self._crear_nodo(dev, pos, c)

        self._actualizar_enlaces(c)
        self._dibujar_pie(c)
        self._canvas.draw_idle()

    def _dibujar_pie(self, c: dict) -> None:
        self._ax.text(
            0.01,
            0.02,
            (
                f"Total: {len(self._dispositivos)} dispositivo(s) — "
                "arrastra el fondo para mover la vista · arrastra un nodo para reorganizar"
            ),
            transform=self._ax.transAxes,
            ha="left",
            va="bottom",
            color=c["text_muted"],
            fontsize=9,
        )
        self._dibujar_leyenda(c)

    _ESTILOS_TIPO = {
        TipoDispositivo.ROUTER: {
            "fill": "#FF9800",
            "edge": "#E65100",
            "ancho": 1.08,
            "alto_base": 0.42,
        },
        TipoDispositivo.ESTE_EQUIPO: {
            "fill": "#4CAF50",
            "edge": "#2E7D32",
            "ancho": 1.0,
            "alto_base": 0.42,
        },
        TipoDispositivo.PC: {
            "fill": "#1E88E5",
            "edge": "#0D47A1",
            "ancho": 0.95,
            "alto_base": 0.4,
        },
        TipoDispositivo.ANDROID: {
            "fill": "#3DDC84",
            "edge": "#1B5E20",
            "ancho": 0.95,
            "alto_base": 0.4,
        },
        TipoDispositivo.TELEFONO: {
            "fill": "#AB47BC",
            "edge": "#6A1B9A",
            "ancho": 0.92,
            "alto_base": 0.4,
        },
        TipoDispositivo.TABLET: {
            "fill": "#26A69A",
            "edge": "#00695C",
            "ancho": 0.92,
            "alto_base": 0.4,
        },
        TipoDispositivo.CHROMECAST: {
            "fill": "#0B8043",
            "edge": "#1B5E20",
            "ancho": 0.95,
            "alto_base": 0.4,
        },
        TipoDispositivo.CAMARA: {
            "fill": "#E53935",
            "edge": "#B71C1C",
            "ancho": 0.92,
            "alto_base": 0.4,
        },
        TipoDispositivo.IOT: {
            "fill": "#78909C",
            "edge": "#455A64",
            "ancho": 0.88,
            "alto_base": 0.38,
        },
        TipoDispositivo.DESCONOCIDO: {
            "fill": "#42A5F5",
            "edge": "#1565C0",
            "ancho": 0.92,
            "alto_base": 0.38,
        },
    }

    _ORDEN_LEYENDA = (
        TipoDispositivo.ROUTER,
        TipoDispositivo.ESTE_EQUIPO,
        TipoDispositivo.PC,
        TipoDispositivo.ANDROID,
        TipoDispositivo.TELEFONO,
        TipoDispositivo.TABLET,
        TipoDispositivo.CHROMECAST,
        TipoDispositivo.CAMARA,
        TipoDispositivo.IOT,
        TipoDispositivo.DESCONOCIDO,
    )

    def _dibujar_leyenda(self, c: dict) -> None:
        presentes = {d.tipo for d in self._dispositivos}
        items = [t for t in self._ORDEN_LEYENDA if t in presentes]
        if not items:
            return

        x = 0.99
        y = 0.02
        ancho_caja = 0.018
        alto_caja = 0.028
        paso = 0.11
        for tipo in reversed(items):
            estilo = self._ESTILOS_TIPO[tipo]
            etiqueta = _ETIQUETAS_TIPO.get(tipo, tipo.value)
            patch = FancyBboxPatch(
                (x - ancho_caja, y),
                ancho_caja,
                alto_caja,
                boxstyle="round,pad=0.01,rounding_size=0.002",
                facecolor=estilo["fill"],
                edgecolor=estilo["edge"],
                linewidth=1.0,
                alpha=0.95,
                transform=self._ax.transAxes,
                clip_on=False,
            )
            self._ax.add_patch(patch)
            self._ax.text(
                x - ancho_caja - 0.008,
                y + alto_caja / 2,
                etiqueta,
                transform=self._ax.transAxes,
                ha="right",
                va="center",
                color=c["text_muted"],
                fontsize=8,
            )
            x -= paso

    def _crear_nodo(
        self,
        dev: DispositivoRed,
        pos: tuple[float, float],
        c: dict,
    ) -> _NodoArt:
        estilo = self._ESTILOS_TIPO.get(dev.tipo, self._ESTILOS_TIPO[TipoDispositivo.DESCONOCIDO])
        detalle = dev.lineas_detalle
        n_lineas = 1 + len(detalle)
        spacing = 0.085
        alto = estilo["alto_base"] + max(0, n_lineas - 2) * spacing
        ancho = estilo["ancho"]
        if detalle and len(detalle[-1]) > 14:
            ancho = max(ancho, 1.05)

        x, y = pos
        caja = FancyBboxPatch(
            (x - ancho / 2, y - alto / 2),
            ancho,
            alto,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=estilo["fill"],
            edgecolor=estilo["edge"],
            linewidth=1.5,
            alpha=0.92,
            picker=True,
        )
        self._ax.add_patch(caja)

        lineas = [dev.etiqueta_rol] + detalle
        total_h = spacing * (len(lineas) - 1)
        start_y = total_h / 2
        textos: list[tuple[Text, float]] = []
        for i, texto in enumerate(lineas):
            dy = start_y - i * spacing
            es_badge = i == 0
            es_mac = i == len(lineas) - 1 and dev.mac and texto == dev.mac
            t = self._ax.text(
                x,
                y + dy,
                texto,
                ha="center",
                va="center",
                color="white",
                fontsize=8 if es_badge else (6.5 if es_mac else 7),
                fontweight="bold" if es_badge else "normal",
                alpha=0.95 if es_badge else (0.85 if es_mac else 0.92),
            )
            textos.append((t, dy))

        return _NodoArt(dev=dev, ancho=ancho, alto=alto, caja=caja, textos=textos)

    def _actualizar_enlaces(self, c: dict | None = None) -> None:
        if c is None:
            c = colores_tema(self._theme)
        for enlace in self._enlaces:
            enlace.remove()
        self._enlaces.clear()

        if not self._hub_ip or self._hub_ip not in self._posiciones:
            return

        hub = self._posiciones[self._hub_ip]
        for ip, pos in self._posiciones.items():
            if ip == self._hub_ip:
                continue
            flecha = FancyArrowPatch(
                hub,
                pos,
                arrowstyle="-",
                color=c["grid"],
                linewidth=1.2,
                alpha=0.55,
                linestyle="--",
                mutation_scale=1,
            )
            self._ax.add_patch(flecha)
            self._enlaces.append(flecha)

    def _nodo_bajo_cursor(self, x: float, y: float) -> str | None:
        for ip, nodo in self._nodos.items():
            nx, ny = self._posiciones[ip]
            if abs(x - nx) <= nodo.ancho / 2 and abs(y - ny) <= nodo.alto / 2:
                return ip
        return None

    def _mover_nodo(self, ip: str, x: float, y: float) -> None:
        self._posiciones[ip] = (x, y)
        nodo = self._nodos[ip]
        nodo.caja.set_x(x - nodo.ancho / 2)
        nodo.caja.set_y(y - nodo.alto / 2)
        for texto, dy in nodo.textos:
            texto.set_position((x, y + dy))
        self._actualizar_enlaces()
        self._canvas.draw_idle()

    def _on_press(self, event) -> None:
        if event.inaxes != self._ax or event.xdata is None or event.ydata is None:
            return
        ip = self._nodo_bajo_cursor(event.xdata, event.ydata)
        if ip:
            self._drag_ip = ip
            nx, ny = self._posiciones[ip]
            self._drag_offset = (nx - event.xdata, ny - event.ydata)
            self._canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        self._panning = True
        self._pan_start = (event.xdata, event.ydata)
        self._pan_view_start = (self._pan_x, self._pan_y)
        self._canvas.setCursor(Qt.CursorShape.OpenHandCursor)

    def _on_motion(self, event) -> None:
        if event.inaxes != self._ax or event.xdata is None or event.ydata is None:
            return

        if self._panning:
            dx = event.xdata - self._pan_start[0]
            dy = event.ydata - self._pan_start[1]
            self._pan_x = self._pan_view_start[0] - dx
            self._pan_y = self._pan_view_start[1] - dy
            self._aplicar_vista()
            return

        if self._drag_ip is not None:
            self._mover_nodo(
                self._drag_ip,
                event.xdata + self._drag_offset[0],
                event.ydata + self._drag_offset[1],
            )

    def _on_release(self, _event) -> None:
        if self._drag_ip is not None or self._panning:
            self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self._drag_ip = None
        self._panning = False

    def figura(self) -> Figure:
        return self._fig
