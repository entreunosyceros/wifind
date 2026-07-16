"""Pestaña de dispositivos conectados a la red local."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QFileDialog,
)

from wifind.modelos.dispositivo_red import (
    ContextoLan,
    DispositivoRed,
    RolDispositivo,
    TipoDispositivo,
)
from wifind.modelos.preferencias import PreferenciasApp
from wifind.servicios.descubrimiento_lan import (
    descubrir_dispositivos,
    obtener_contexto_lan,
    pista_error_descubrimiento,
)
from wifind.servicios.exportacion import exportar_figura_png
from wifind.ui.grafico_dispositivos import GraficoDispositivos


class HiloDescubrimiento(QThread):
    progreso = pyqtSignal(str, int)
    terminado = pyqtSignal(list)
    fallo = pyqtSignal(str)

    def __init__(
        self,
        contexto: ContextoLan,
        *,
        enable_light_port_scan: bool,
        light_port_timeout_ms: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._contexto = contexto
        self._enable_light_port_scan = enable_light_port_scan
        self._light_port_timeout_ms = light_port_timeout_ms

    def run(self) -> None:
        try:
            dispositivos = descubrir_dispositivos(
                self._contexto,
                progreso=lambda msg, pct: self.progreso.emit(msg, pct),
                enable_light_port_scan=self._enable_light_port_scan,
                light_port_timeout_ms=self._light_port_timeout_ms,
            )
            self.terminado.emit(dispositivos)
        except Exception as exc:
            self.fallo.emit(str(exc))


class PestanaDispositivos(QWidget):
    colocar_router_solicitado = pyqtSignal(str)

    def __init__(self, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.prefs = prefs
        self._contexto: ContextoLan | None = None
        self._dispositivos: list[DispositivoRed] = []
        self._hilo: HiloDescubrimiento | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        intro = QLabel(
            "Explora los dispositivos en la misma red WiFi una vez conectado. "
            "El diagrama muestra el router/gateway (centro), este equipo (abajo) y el resto alrededor. "
            "El gateway se marca automáticamente como router. "
            "Arrastra el fondo para mover la vista o un nodo para reorganizarlo."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.context_label = QLabel("Sin conexión WiFi activa con IP asignada.")
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)

        bar = QHBoxLayout()
        self.scan_btn = QPushButton("Escanear dispositivos")
        self.scan_btn.clicked.connect(self.iniciar_escaneo)
        self.scan_btn.setEnabled(False)
        bar.addWidget(self.scan_btn)

        self.export_btn = QPushButton("Exportar diagrama (PNG)")
        self.export_btn.clicked.connect(self.exportar_diagrama)
        self.export_btn.setEnabled(False)
        bar.addWidget(self.export_btn)

        self.place_router_btn = QPushButton("Colocar router en el mapa")
        self.place_router_btn.clicked.connect(self.solicitar_colocar_router)
        self.place_router_btn.setEnabled(False)
        bar.addWidget(self.place_router_btn)

        self.status_label = QLabel("")
        bar.addWidget(self.status_label, stretch=1)
        layout.addLayout(bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% — %v")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.grafico = GraficoDispositivos()
        splitter.addWidget(self.grafico)

        self.table = QTableWidget(0, 5)
        self.table.setMinimumHeight(120)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.actualizar_contexto()

    def actualizar_contexto(self) -> None:
        self._contexto = obtener_contexto_lan()
        conectado = self._contexto is not None
        self.scan_btn.setEnabled(conectado and self._hilo is None)

        if self._contexto:
            ctx = self._contexto
            self.context_label.setText(
                f"<b>Red:</b> {ctx.ssid} — "
                f"<b>IP:</b> {ctx.ip}/{ctx.prefix} — "
                f"<b>Gateway / router:</b> {ctx.gateway or '—'}"
            )
            self.place_router_btn.setEnabled(bool(ctx.gateway) or bool(self._dispositivos))
        else:
            self.context_label.setText(
                "Conéctate a una red WiFi para explorar los dispositivos de la LAN."
            )
            self.place_router_btn.setEnabled(False)
            if not self._dispositivos:
                self.grafico.actualizar([], theme=self.prefs.theme)

    def iniciar_escaneo(self) -> None:
        if self._hilo is not None:
            return
        self._contexto = obtener_contexto_lan()
        if not self._contexto:
            QMessageBox.information(
                self,
                "Dispositivos en la red",
                "No hay conexión WiFi activa con IP asignada.\n\nConéctate primero desde el escáner.",
            )
            return

        self.scan_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self._mostrar_progreso("Iniciando escaneo…", 0)

        self._hilo = HiloDescubrimiento(
            self._contexto,
            enable_light_port_scan=self.prefs.enable_light_port_scan,
            light_port_timeout_ms=self.prefs.light_port_timeout_ms,
            parent=self,
        )
        self._hilo.progreso.connect(self._on_progreso)
        self._hilo.terminado.connect(self._on_terminado)
        self._hilo.fallo.connect(self._on_fallo)
        self._hilo.finished.connect(self._hilo_finalizado)
        self._hilo.start()

    def _mostrar_progreso(self, msg: str, porcentaje: int) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(porcentaje)
        self.progress_bar.setFormat(f"%p% — {msg}")
        self.status_label.setText(msg)

    def _ocultar_progreso(self) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

    def _on_progreso(self, msg: str, porcentaje: int) -> None:
        self._mostrar_progreso(msg, porcentaje)

    def _on_terminado(self, dispositivos: list) -> None:
        self._dispositivos = dispositivos
        ssid = self._contexto.ssid if self._contexto else ""
        self.grafico.actualizar(dispositivos, ssid=ssid, theme=self.prefs.theme)
        self._rellenar_tabla(dispositivos)
        n = len(dispositivos)
        self._mostrar_progreso(f"{n} dispositivo(s) detectado(s)", 100)
        self._ocultar_progreso()
        self.status_label.setText(f"{n} dispositivo(s) detectado(s).")
        self.export_btn.setEnabled(n > 0)
        self.place_router_btn.setEnabled(
            any(d.rol == RolDispositivo.GATEWAY or d.tipo == TipoDispositivo.ROUTER for d in dispositivos)
        )
        if n == 0:
            QMessageBox.information(
                self,
                "Dispositivos en la red",
                "No se detectaron otros dispositivos.\n\n" + pista_error_descubrimiento(),
            )

    def _on_fallo(self, msg: str) -> None:
        self._ocultar_progreso()
        self.status_label.setText("Error en el escaneo.")
        QMessageBox.warning(
            self,
            "Error",
            f"{msg}\n\n{pista_error_descubrimiento()}",
        )

    def _hilo_finalizado(self) -> None:
        self._hilo = None
        self._ocultar_progreso()
        self.scan_btn.setEnabled(self._contexto is not None)

    def _rellenar_tabla(self, dispositivos: list[DispositivoRed]) -> None:
        self.table.setRowCount(len(dispositivos))
        colores_tipo = {
            TipoDispositivo.ROUTER: ("#E65100", "#FFF3E0"),
            TipoDispositivo.ESTE_EQUIPO: ("#2E7D32", "#E8F5E9"),
            TipoDispositivo.PC: ("#0D47A1", "#E3F2FD"),
            TipoDispositivo.CHROMECAST: ("#0B8043", "#E6F4EA"),
            TipoDispositivo.CAMARA: ("#B71C1C", "#FFEBEE"),
            TipoDispositivo.ANDROID: ("#1B5E20", "#E8F5E9"),
            TipoDispositivo.TELEFONO: ("#6A1B9A", "#F3E5F5"),
            TipoDispositivo.TABLET: ("#00695C", "#E0F2F1"),
            TipoDispositivo.IOT: ("#455A64", "#ECEFF1"),
            TipoDispositivo.DESCONOCIDO: ("#1565C0", "#E3F2FD"),
        }
        for row, dev in enumerate(dispositivos):
            valores = [
                dev.tipo_legible,
                dev.ip,
                dev.mac or "—",
                dev.hostname or "—",
                "Activo" if dev.activo else "Inactivo",
            ]
            fg, bg = colores_tipo.get(dev.tipo, ("#424242", "#FAFAFA"))
            for col, texto in enumerate(valores):
                item = QTableWidgetItem(texto)
                item.setForeground(QColor(fg))
                if col == 0:
                    item.setBackground(QColor(bg))
                self.table.setItem(row, col, item)

    def exportar_diagrama(self) -> None:
        if not self._dispositivos:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar diagrama de dispositivos",
            str(self.prefs.export_dir or "") + "/dispositivos_red.png",
            "PNG (*.png)",
        )
        if not path:
            return
        exportar_figura_png(self.grafico.figura(), path, dpi=150)
        self.status_label.setText(f"Diagrama guardado: {path}")

    @property
    def dispositivos(self) -> list[DispositivoRed]:
        return list(self._dispositivos)

    def solicitar_colocar_router(self) -> None:
        gateway = next(
            (d for d in self._dispositivos if d.rol == RolDispositivo.GATEWAY),
            None,
        )
        if gateway is None:
            gateway = next(
                (d for d in self._dispositivos if d.tipo == TipoDispositivo.ROUTER),
                None,
            )
        if gateway is None and self._contexto and self._contexto.gateway:
            nombre = f"Router ({self._contexto.gateway})"
        elif gateway is not None:
            nombre = gateway.hostname or f"Router ({gateway.ip})"
        else:
            nombre = "Router"
        self.colocar_router_solicitado.emit(nombre)

    def refrescar_tema(self) -> None:
        if self._dispositivos and self._contexto:
            self.grafico.actualizar(
                self._dispositivos,
                ssid=self._contexto.ssid,
                theme=self.prefs.theme,
            )
