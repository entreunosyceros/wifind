"""Ventana principal de WiFind."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from wifind import __app_name__, __version__
from wifind.mapa_calor import construir_figura_mapa_calor, construir_figura_intensidad
from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.instantanea_escaneo import InstantaneaEscaneo
from wifind.modelos.sesion import SesionApp
from wifind.servicios.exportacion import (
    exportar_figura_pdf,
    exportar_figura_png,
    exportar_mediciones_csv,
    exportar_redes_csv,
)
from wifind.servicios.informe import generar_informe_html
from wifind.ui.dialogo_acerca import DialogoAcerca
from wifind.ui.dialogo_manual import DialogoManual
from wifind.ui.dialogo_preferencias import DialogoPreferencias
from wifind.ui.pestanas.pestana_canales import PestanaCanales
from wifind.ui.pestanas.pestana_mapa_calor import PestanaMapaCalor
from wifind.ui.pestanas.pestana_historico import PestanaHistorico
from wifind.ui.pestanas.pestana_intensidad import PestanaIntensidad
from wifind.ui.pestanas.pestana_escaner import PestanaEscaner
from wifind.ui.pestanas.pestana_dispositivos import PestanaDispositivos
from wifind.ui.temas import aplicar_tema
from wifind.wifi.red import RedWifi
from wifind.wifi.plataforma import pista_error_escaneo, escanear_redes


def ruta_icono_app() -> Path:
    return Path(__file__).resolve().parents[1] / "img" / "logo.png"


MENSAJE_CIERRE_CTRL_C = (
    "\nWiFind: interrupción por teclado (Ctrl+C).\n"
    "Cerrando la aplicación de forma segura…\n"
    "Para volver a iniciar: python3 run_app.py\n"
)


def _configurar_cierre_ctrl_c(app: QApplication) -> None:
    """Permite cerrar WiFind con Ctrl+C sin traceback ni core dump."""
    interrumpido = {"valor": False}

    def manejar_sigint(_signum, _frame) -> None:
        if interrumpido["valor"]:
            print("\nWiFind: segunda interrupción — salida inmediata.", flush=True)
            sys.exit(130)
        interrumpido["valor"] = True
        print(MENSAJE_CIERRE_CTRL_C, flush=True)
        app.quit()

    signal.signal(signal.SIGINT, manejar_sigint)
    # Sin este timer, el bucle de Qt bloquea el procesamiento de señales de Python.
    timer = QTimer(app)
    timer.timeout.connect(lambda: None)
    timer.start(400)


class VentanaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} — Mapa de calor WiFi")
        self.resize(1200, 780)

        self.prefs = PreferenciasApp.load()
        self.session = SesionApp.new()
        self._networks: list[RedWifi] = []
        self._dirty = False

        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self._configurar_bandeja_sistema()
        self.conectar_signals()

        from PyQt6.QtCore import QTimer

        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(self.prefs.scan_interval_ms)
        self._scan_timer.timeout.connect(self.actualizar_escaneo)

        aplicar_tema(QApplication.instance(), self.prefs.theme)
        self.actualizar_escaneo()
        self._scan_timer.start()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        header = QLabel(f"{__app_name__} v{__version__}")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        header.setFont(font)
        root.addWidget(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.scanner_tab = PestanaEscaner(self.prefs)
        self.intensity_tab = PestanaIntensidad(self.session, self.prefs)
        self.heatmap_tab = PestanaMapaCalor(self.session, self.prefs)
        self.channels_tab = PestanaCanales(self.prefs)
        self.history_tab = PestanaHistorico(self.session, self.prefs)
        self.devices_tab = PestanaDispositivos(self.prefs)

        self.tabs.addTab(self.scanner_tab, "Escáner WiFi")
        self.tabs.addTab(self.intensity_tab, "Intensidad en vivo")
        self.tabs.addTab(self.heatmap_tab, "Mapa de calor")
        self.tabs.addTab(self.channels_tab, "Canales")
        self.tabs.addTab(self.devices_tab, "Dispositivos")
        self.tabs.addTab(self.history_tab, "Histórico")

    def _build_menus(self) -> None:
        mb = QMenuBar(self)
        self.setMenuBar(mb)

        file_menu = mb.addMenu("Archivo")
        self._poblar_menu_archivo(file_menu, atajos=True)

        view_menu = mb.addMenu("Ver")
        self.floors_menu = view_menu.addMenu("Plantas")
        self.reconstruir_menu_plantas()
        view_menu.addAction("Tema claro", lambda: self.establecer_tema("light"))
        view_menu.addAction("Tema oscuro", lambda: self.establecer_tema("dark"))

        options_menu = mb.addMenu("Opciones")
        options_menu.addAction("Manual…", self.mostrar_manual)
        options_menu.addAction("Preferencias…", self.mostrar_preferencias)
        options_menu.addAction("About", self.mostrar_acerca)

    def _poblar_menu_archivo(self, menu: QMenu, *, atajos: bool = False) -> None:
        def accion(texto: str, slot, atajo=None):
            if atajos and atajo is not None:
                menu.addAction(texto, atajo, slot)
            else:
                menu.addAction(texto, slot)

        accion("Nueva sesión", self.nueva_sesion, QKeySequence.StandardKey.New)
        accion("Abrir sesión…", self.abrir_sesion, QKeySequence.StandardKey.Open)
        accion("Guardar sesión", self.guardar_sesion, QKeySequence.StandardKey.Save)
        accion("Guardar sesión como…", self.guardar_sesion_como)
        menu.addSeparator()
        accion("Cargar plano de planta…", self.cargar_plano)
        accion("Quitar plano de planta", self.quitar_plano)
        menu.addSeparator()

        export_menu = menu.addMenu("Exportar")
        export_menu.addAction("Mapa de calor (PNG)", lambda: self.exportar_mapa_calor("png"))
        export_menu.addAction("Mapa de calor (PDF)", lambda: self.exportar_mapa_calor("pdf"))
        export_menu.addAction("Intensidad (PNG)", lambda: self.exportar_intensidad("png"))
        export_menu.addAction("Intensidad (PDF)", lambda: self.exportar_intensidad("pdf"))
        export_menu.addAction("Redes escaneadas (CSV)", self.exportar_redes_csv)
        export_menu.addAction("Mediciones (CSV)", self.exportar_mediciones_csv)

        accion("Generar informe…", self.generar_informe)
        menu.addSeparator()
        accion("Salir", self.close, QKeySequence("Ctrl+Q"))

    def _configurar_bandeja_sistema(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.status.showMessage("Bandeja del sistema no disponible en este entorno")
            return

        icon_path = ruta_icono_app()
        icon = QIcon(str(icon_path)) if icon_path.is_file() else self.windowIcon()
        if icon.isNull():
            return

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip(f"{__app_name__} — Mapa de calor WiFi")

        tray_menu = QMenu(self)
        self._poblar_menu_archivo(tray_menu, atajos=False)
        self._tray_icon.setContextMenu(tray_menu)

        self._tray_icon.activated.connect(self._tray_icono_activado)
        self._tray_icon.show()

    def _tray_icono_activado(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principal")
        self.addToolBar(tb)
        tb.addAction("Escanear", self.actualizar_escaneo)
        self.auto_scan = QAction("Auto-escaneo", self)
        self.auto_scan.setCheckable(True)
        self.auto_scan.setChecked(True)
        self.auto_scan.toggled.connect(self.alternar_auto_escaneo)
        tb.addAction(self.auto_scan)

    def _build_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo")

    def conectar_signals(self) -> None:
        self.scanner_tab.conexion_solicitada.connect(self.actualizar_escaneo)
        self.scanner_tab.monitorizacion_solicitada.connect(self.ir_a_monitor)
        self.scanner_tab.mapa_calor_solicitado.connect(self.ir_a_mapa_calor)
        self.scanner_tab.dispositivos_solicitados.connect(self.ir_a_dispositivos)
        self.heatmap_tab.planta_cambiada.connect(self.reconstruir_menu_plantas)

    def reconstruir_menu_plantas(self) -> None:
        self.floors_menu.clear()
        for floor in self.session.floors:
            action = self.floors_menu.addAction(floor.name)
            action.triggered.connect(
                lambda checked=False, fid=floor.id: self.seleccionar_planta(fid)
            )

    def seleccionar_planta(self, floor_id: str) -> None:
        self.session.planta_activa_id = floor_id
        idx = self.heatmap_tab.floor_combo.findData(floor_id)
        if idx >= 0:
            self.heatmap_tab.floor_combo.setCurrentIndex(idx)
        self.heatmap_tab.sincronizar_desde_planta()

    def alternar_auto_escaneo(self, enabled: bool) -> None:
        if enabled:
            self._scan_timer.start()
        else:
            self._scan_timer.stop()

    def actualizar_escaneo(self) -> None:
        self.status.showMessage("Escaneando…")
        QApplication.processEvents()
        try:
            networks = escanear_redes()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"{exc}\n\n{pista_error_escaneo()}")
            return

        self._networks = networks
        snap = InstantaneaEscaneo.desde_redes(networks)
        self.session.scan_history.append(snap)
        if len(self.session.scan_history) > 100:
            self.session.scan_history = self.session.scan_history[-100:]

        self.scanner_tab.establecer_redes(networks)
        self.intensity_tab.establecer_redes(networks)
        self.heatmap_tab.establecer_redes(networks)
        self.channels_tab.establecer_redes(networks)
        avg = snap.senal_media_dbm
        self.history_tab.refresh(len(networks), avg)
        self.devices_tab.actualizar_contexto()
        self.status.showMessage(f"{len(networks)} redes detectadas")

    def ir_a_monitor(self, ssid: str) -> None:
        self.intensity_tab.establecer_ssid_monitor(ssid)
        self.tabs.setCurrentWidget(self.intensity_tab)

    def ir_a_mapa_calor(self, ssid: str) -> None:
        self.heatmap_tab.establecer_ssid_objetivo(ssid)
        self.tabs.setCurrentWidget(self.heatmap_tab)

    def ir_a_dispositivos(self) -> None:
        self.devices_tab.actualizar_contexto()
        self.tabs.setCurrentWidget(self.devices_tab)
        self.devices_tab.iniciar_escaneo()

    def directorio_exportacion(self) -> Path:
        if self.prefs.export_dir:
            p = Path(self.prefs.export_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return Path.home()

    def exportar_mapa_calor(self, fmt: str) -> None:
        floor = self.session.planta_activa
        fig = construir_figura_mapa_calor(
            floor.measurements,
            self.heatmap_tab.ssid_combo.currentText(),
            floor.x_max,
            floor.y_max,
            floor.floor_plan_path,
            self.prefs.threshold_fair,
            True,
            floor.waypoints,
            None,
            floor.obstaculos,
            unit_suffix=self.prefs.sufijo_longitud(),
            theme=self.prefs.theme,
        )
        ext = fmt
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar mapa", str(self.directorio_exportacion() / f"heatmap.{ext}"), f"*.{ext}"
        )
        if not path:
            return
        if fmt == "png":
            exportar_figura_png(fig, path)
        else:
            exportar_figura_pdf(fig, path)
        self.status.showMessage(f"Exportado: {path}")

    def exportar_intensidad(self, fmt: str) -> None:
        fig = construir_figura_intensidad(
            self.session.intensity.timestamps,
            self.session.intensity.values_dbm,
            self.session.intensity.ssid,
            self.prefs.thresholds,
            theme=self.prefs.theme,
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar intensidad", str(self.directorio_exportacion() / f"intensity.{fmt}"), f"*.{fmt}"
        )
        if not path:
            return
        if fmt == "png":
            exportar_figura_png(fig, path)
        else:
            exportar_figura_pdf(fig, path)

    def exportar_redes_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar redes", str(self.directorio_exportacion() / "networks.csv"), "*.csv"
        )
        if path:
            exportar_redes_csv(self._networks, path)
            self.status.showMessage(f"Exportado: {path}")

    def exportar_mediciones_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar mediciones", str(self.directorio_exportacion() / "measurements.csv"), "*.csv"
        )
        if path:
            all_m = [m for f in self.session.floors for m in f.measurements]
            exportar_mediciones_csv(all_m, path)
            self.status.showMessage(f"Exportado: {path}")

    def generar_informe(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Generar informe", str(self.directorio_exportacion() / "informe.html"), "*.html"
        )
        if not path:
            return
        generar_informe_html(self.session, self._networks, self.prefs, path)
        self.status.showMessage(f"Informe: {path}")

    def nueva_sesion(self) -> None:
        if self.confirmar_descartar():
            self.session = SesionApp.new()
            self.heatmap_tab.session = self.session
            self.intensity_tab.session = self.session
            self.history_tab.session = self.session
            self.heatmap_tab.actualizar_plantas()
            self.heatmap_tab.sincronizar_desde_planta()
            self.history_tab.refresh()
            self._dirty = False

    def abrir_sesion(self) -> None:
        if not self.confirmar_descartar():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir sesión", "", "WiFind (*.wifind)")
        if not path:
            return
        try:
            self.session = SesionApp.load(Path(path))
            self.aplicar_sesion()
            self.status.showMessage(f"Sesión cargada: {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo abrir la sesión:\n{exc}")

    def guardar_sesion(self) -> None:
        if self.session.file_path:
            self.session.save(Path(self.session.file_path))
            self._dirty = False
            self.status.showMessage("Sesión guardada")
        else:
            self.guardar_sesion_como()

    def guardar_sesion_como(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar sesión", str(Path.home() / "proyecto.wifind"), "WiFind (*.wifind)"
        )
        if path:
            self.session.save(Path(path))
            self._dirty = False
            self.status.showMessage(f"Sesión guardada: {path}")

    def aplicar_sesion(self) -> None:
        self.heatmap_tab.session = self.session
        self.intensity_tab.session = self.session
        self.history_tab.session = self.session
        self.heatmap_tab.actualizar_plantas()
        self.heatmap_tab.sincronizar_desde_planta()
        self.intensity_tab.dibujar()
        self.history_tab.refresh()

    def confirmar_descartar(self) -> bool:
        if not self._dirty:
            return True
        r = QMessageBox.question(
            self, "WiFind", "¿Descartar cambios sin guardar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return r == QMessageBox.StandardButton.Yes

    def cargar_plano(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Plano", str(Path.home()),
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if path and self.heatmap_tab.cargar_plano_planta(path):
            self.tabs.setCurrentWidget(self.heatmap_tab)
            self._dirty = True

    def quitar_plano(self) -> None:
        self.heatmap_tab.quitar_plano_planta()
        self._dirty = True

    def _refrescar_graficos(self) -> None:
        self.intensity_tab.dibujar()
        self.heatmap_tab.canvas.redraw()
        if self._networks:
            self.channels_tab.establecer_redes(self._networks)
        self.history_tab.refresh()
        self.devices_tab.refrescar_tema()

    def mostrar_manual(self) -> None:
        DialogoManual(self).exec()

    def mostrar_preferencias(self) -> None:
        dlg = DialogoPreferencias(self.prefs, self)
        if dlg.exec():
            dlg.aplicar_a(self.prefs)
            self._scan_timer.setInterval(self.prefs.scan_interval_ms)
            aplicar_tema(QApplication.instance(), self.prefs.theme)
            self.scanner_tab.prefs = self.prefs
            self.intensity_tab.prefs = self.prefs
            self.heatmap_tab.prefs = self.prefs
            self.channels_tab.prefs = self.prefs
            self.devices_tab.prefs = self.prefs
            self.history_tab.prefs = self.prefs
            self._refrescar_graficos()

    def mostrar_acerca(self) -> None:
        DialogoAcerca(self).exec()

    def establecer_tema(self, theme: str) -> None:
        self.prefs.theme = theme
        self.prefs.save()
        aplicar_tema(QApplication.instance(), theme)
        self._refrescar_graficos()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_F5:
            self.actualizar_escaneo()
        elif event.matches(QKeySequence.StandardKey.Save):
            self.guardar_sesion()
        elif event.matches(QKeySequence.StandardKey.Open):
            self.abrir_sesion()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self.heatmap_tab.deshacer_accion()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.confirmar_descartar():
            event.accept()
        else:
            event.ignore()


def ejecutar_app() -> None:
    if sys.platform == "win32":
        import matplotlib

        matplotlib.use("QtAgg")

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("WiFind")
    _configurar_cierre_ctrl_c(app)

    icon_path = ruta_icono_app()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = VentanaPrincipal()
    window.show()
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        print(MENSAJE_CIERRE_CTRL_C, flush=True)
        exit_code = 0
    print("WiFind cerrado.", flush=True)
    sys.exit(exit_code)


if __name__ == "__main__":
    ejecutar_app()
