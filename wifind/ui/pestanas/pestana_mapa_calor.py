"""Pestaña mapa de calor."""

from __future__ import annotations

import time

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wifind.mapa_calor import (
    color_material,
    dibujar_mapa_calor_comparacion_en,
    dibujar_mapa_calor_en,
)
from wifind.modelos.medicion import Medicion, Obstaculo, PuntoRuta, MATERIALES_PARED, atenuacion_material
from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import SesionApp, NivelPlanta
from wifind.servicios.cobertura import calcular_estadisticas_cobertura
from wifind.servicios.recorrido import MotorRecorrido
from wifind.wifi.plataforma import obtener_red_conectada


class DialogoEditarPared(QDialog):
    def __init__(self, obstaculo: Obstaculo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar pared")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.material_combo = QComboBox()
        for key, (label, _) in MATERIALES_PARED.items():
            self.material_combo.addItem(label, key)
        idx = max(0, self.material_combo.findData(obstaculo.material))
        self.material_combo.setCurrentIndex(idx)
        self.atenuacion_spin = QDoubleSpinBox()
        self.atenuacion_spin.setRange(0.5, 50.0)
        self.atenuacion_spin.setSuffix(" dB")
        self.atenuacion_spin.setDecimals(1)
        self.atenuacion_spin.setSingleStep(0.5)
        self.atenuacion_spin.setValue(obstaculo.atenuacion_db)
        form.addRow("Material:", self.material_combo)
        form.addRow("Atenuación:", self.atenuacion_spin)
        layout.addLayout(form)
        self.material_combo.currentIndexChanged.connect(self._material_cambiado)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _material_cambiado(self) -> None:
        key = self.material_combo.currentData()
        if key != "personalizado":
            self.atenuacion_spin.setValue(atenuacion_material(key))

    def resultado(self) -> tuple[str, float]:
        return self.material_combo.currentData(), self.atenuacion_spin.value()


class LienzoMapaCalor(FigureCanvasQTAgg):
    def __init__(self, tab: "PestanaMapaCalor", parent=None) -> None:
        self.tab = tab
        self._drag_idx: int | None = None
        self._cal_start: tuple[float, float] | None = None
        self._wall_start: tuple[float, float] | None = None
        self._wall_preview_line = None
        figure = Figure(figsize=(6, 5), dpi=100)
        super().__init__(figure)
        self.setParent(parent)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("motion_notify_event", self._on_motion)

    def redraw(self) -> None:
        self._limpiar_preview_pared()
        floor = self.tab.session.planta_activa
        prefs = self.tab.prefs
        cal = floor.calibration
        cal_line = None
        if cal.real_length_m > 0:
            cal_line = (cal.x1, cal.y1, cal.x2, cal.y2)

        fig = self.figure
        fig.clear()

        compare = self.tab.compare_list.selectedItems()
        if len(compare) >= 2:
            by_ssid = {}
            for item in compare:
                ssid = item.text()
                by_ssid[ssid] = [m for m in floor.measurements if m.ssid == ssid]
            dibujar_mapa_calor_comparacion_en(
                fig,
                by_ssid,
                floor.x_max,
                floor.y_max,
                floor.floor_plan_path,
                floor.obstaculos,
                prefs.theme,
            )
        else:
            ssid = self.tab.ssid_combo.currentText()
            pts = floor.measurements
            if ssid:
                pts = [m for m in pts if not m.ssid or m.ssid == ssid]
            ax = fig.add_subplot(111)
            dibujar_mapa_calor_en(
                fig,
                ax,
                pts,
                ssid,
                floor.x_max,
                floor.y_max,
                floor.floor_plan_path,
                prefs.threshold_fair,
                True,
                floor.waypoints,
                cal_line,
                floor.obstaculos,
                prefs.sufijo_longitud(),
                theme=prefs.theme,
            )

        self.draw_idle()
        self.tab.actualizar_cobertura()

    def _limpiar_preview_pared(self) -> None:
        if self._wall_preview_line is not None:
            try:
                self._wall_preview_line.remove()
            except (ValueError, AttributeError):
                pass
            self._wall_preview_line = None

    def _actualizar_preview_pared(self, x2: float, y2: float) -> None:
        if self._wall_start is None:
            return
        x1, y1 = self._wall_start
        color = color_material(self.tab.material_pared_combo.currentData())
        ax = self.figure.gca()
        if self._wall_preview_line is None:
            (self._wall_preview_line,) = ax.plot(
                [x1, x2],
                [y1, y2],
                color=color,
                linewidth=4,
                linestyle="--",
                alpha=0.85,
                solid_capstyle="round",
                zorder=10,
            )
        else:
            self._wall_preview_line.set_data([x1, x2], [y1, y2])
            self._wall_preview_line.set_color(color)
        self.draw_idle()

    def _on_press(self, event) -> None:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        x, y = event.xdata, event.ydata
        floor = self.tab.session.planta_activa

        if self.tab.calibrate_mode:
            if event.button == 1:
                self._cal_start = (x, y)
            return

        if self.tab.modo_pared:
            if event.button == 1:
                self._wall_start = (x, y)
            return

        if event.key == "shift" and event.button == 1:
            floor.waypoints.append(PuntoRuta(x=x, y=y))
            self.tab.session.touch()
            self.redraw()
            return

        if event.button == 3:
            wall_idx = self.tab.obstaculo_mas_cercano(x, y)
            if wall_idx is not None:
                self.tab.menu_obstaculo(wall_idx)
                return
            idx = self.tab.punto_mas_cercano(x, y)
            if idx is not None:
                self.tab.menu_punto(idx)
            return

        if event.button == 1:
            idx = self.tab.punto_mas_cercano(x, y, threshold=0.8)
            if idx is not None:
                self._drag_idx = idx
                return
            self.tab.registrar_medicion_en(x, y)

    def _on_release(self, event) -> None:
        if self.tab.calibrate_mode and self._cal_start and event.button == 1:
            if event.xdata is None or event.ydata is None:
                return
            x1, y1 = self._cal_start
            x2, y2 = event.xdata, event.ydata
            length, ok = QInputDialog.getDouble(
                self.tab,
                "Calibración",
                "Longitud real de la línea (m):",
                1.0,
                0.01,
                1000,
                2,
            )
            if ok and length > 0:
                import math

                pixel_dist = math.hypot(x2 - x1, y2 - y1)
                cal = self.tab.session.planta_activa.calibration
                cal.x1, cal.y1, cal.x2, cal.y2 = x1, y1, x2, y2
                cal.real_length_m = length
                cal.pixels_per_meter = pixel_dist / length if length else 0
                if cal.pixels_per_meter > 0:
                    self.tab.session.planta_activa.x_max = max(
                        self.tab.session.planta_activa.x_max,
                        pixel_dist,
                    )
                self.tab.calibrate_mode = False
                self.tab.calibrate_btn.setChecked(False)
                self.tab.session.touch()
            self._cal_start = None
            self.redraw()
            return

        if self.tab.modo_pared and self._wall_start and event.button == 1:
            self._limpiar_preview_pared()
            if event.xdata is None or event.ydata is None:
                self._wall_start = None
                return
            x1, y1 = self._wall_start
            x2, y2 = event.xdata, event.ydata
            import math

            if math.hypot(x2 - x1, y2 - y1) >= 0.15:
                floor = self.tab.session.planta_activa
                floor.obstaculos.append(
                    Obstaculo.desde_material(
                        x1, y1, x2, y2,
                        self.tab.material_pared_combo.currentData(),
                        self.tab.atenuacion_pared_spin.value(),
                    )
                )
                self.tab.session.touch()
            self._wall_start = None
            self.redraw()
            return

        self._drag_idx = None

    def _on_motion(self, event) -> None:
        if (
            self.tab.modo_pared
            and self._wall_start is not None
            and event.xdata is not None
            and event.ydata is not None
        ):
            self._actualizar_preview_pared(event.xdata, event.ydata)
            return
        if self._drag_idx is None or event.xdata is None or event.ydata is None:
            return
        m = self.tab.session.planta_activa.measurements[self._drag_idx]
        m.x = event.xdata
        m.y = event.ydata
        self.redraw()


class PestanaMapaCalor(QWidget):
    planta_cambiada = pyqtSignal()

    def __init__(self, session: SesionApp, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.prefs = prefs
        self._networks = []
        self.calibrate_mode = False
        self.modo_pared = False
        self._undo: list[list] = []
        self._redo: list[list] = []

        self.survey = MotorRecorrido(
            interval_sec=prefs.survey_interval_sec,
            step_y=prefs.walk_step_m,
            advance_y=prefs.auto_survey_advance_y,
        )

        layout = QHBoxLayout(self)
        sidebar = QVBoxLayout()
        layout.addLayout(sidebar, stretch=0)

        form = QFormLayout()
        self.floor_combo = QComboBox()
        self.floor_combo.currentIndexChanged.connect(self.cambiar_planta)
        form.addRow("Planta:", self.floor_combo)

        self.ssid_combo = QComboBox()
        form.addRow("Red objetivo:", self.ssid_combo)

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(1, 200)
        self.x_spin.setValue(10)
        form.addRow("Ancho:", self.x_spin)
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(1, 200)
        self.y_spin.setValue(10)
        form.addRow("Alto:", self.y_spin)
        sidebar.addLayout(form)

        floor_btns = QHBoxLayout()
        anadir_planta = QPushButton("+ Piso")
        anadir_planta.clicked.connect(self.anadir_planta_ui)
        ren_floor = QPushButton("Renombrar")
        ren_floor.clicked.connect(self.renombrar_planta)
        floor_btns.addWidget(anadir_planta)
        floor_btns.addWidget(ren_floor)
        sidebar.addLayout(floor_btns)

        self.compare_list = QListWidget()
        self.compare_list.setMaximumHeight(80)
        self.compare_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        sidebar.addWidget(QLabel("Comparar redes:"))
        sidebar.addWidget(self.compare_list)

        self.measure_btn = QPushButton("Medir en centro")
        self.measure_btn.clicked.connect(self.medir_centro)
        sidebar.addWidget(self.measure_btn)

        self.calibrate_btn = QPushButton("Calibrar plano")
        self.calibrate_btn.setCheckable(True)
        self.calibrate_btn.toggled.connect(self.alternar_calibrar)
        sidebar.addWidget(self.calibrate_btn)

        self.modo_pared_btn = QPushButton("Dibujar paredes")
        self.modo_pared_btn.setCheckable(True)
        self.modo_pared_btn.toggled.connect(self.alternar_modo_pared)
        sidebar.addWidget(self.modo_pared_btn)

        self.material_pared_combo = QComboBox()
        for key, (label, att) in MATERIALES_PARED.items():
            if key == "personalizado":
                self.material_pared_combo.addItem(label, key)
            else:
                self.material_pared_combo.addItem(f"{label} (~{att:.0f} dB)", key)
        self.material_pared_combo.currentIndexChanged.connect(self.material_pared_cambiado)
        sidebar.addWidget(QLabel("Material de pared:"))
        sidebar.addWidget(self.material_pared_combo)

        self.atenuacion_pared_spin = QDoubleSpinBox()
        self.atenuacion_pared_spin.setRange(0.5, 50.0)
        self.atenuacion_pared_spin.setSuffix(" dB")
        self.atenuacion_pared_spin.setDecimals(1)
        self.atenuacion_pared_spin.setSingleStep(0.5)
        self.atenuacion_pared_spin.setValue(atenuacion_material("ladrillo"))
        self.atenuacion_pared_spin.valueChanged.connect(self.atenuacion_pared_cambiada)
        sidebar.addWidget(QLabel("Atenuación:"))
        sidebar.addWidget(self.atenuacion_pared_spin)

        self.limpiar_paredes_btn = QPushButton("Limpiar paredes")
        self.limpiar_paredes_btn.clicked.connect(self.limpiar_paredes)
        sidebar.addWidget(self.limpiar_paredes_btn)

        self.survey_btn = QPushButton("Iniciar recorrido auto")
        self.survey_btn.setCheckable(True)
        self.survey_btn.toggled.connect(self.alternar_recorrido)
        sidebar.addWidget(self.survey_btn)

        self.waypoint_btn = QPushButton("Registrar waypoint")
        self.waypoint_btn.clicked.connect(self.registrar_punto_ruta)
        sidebar.addWidget(self.waypoint_btn)

        undo_row = QHBoxLayout()
        self.undo_btn = QPushButton("Deshacer")
        self.undo_btn.clicked.connect(self.deshacer_accion)
        self.redo_btn = QPushButton("Rehacer")
        self.redo_btn.clicked.connect(self.rehacer_accion)
        undo_row.addWidget(self.undo_btn)
        undo_row.addWidget(self.redo_btn)
        sidebar.addLayout(undo_row)

        self.clear_btn = QPushButton("Limpiar mediciones")
        self.clear_btn.clicked.connect(self.limpiar)
        sidebar.addWidget(self.clear_btn)

        self.floor_plan_label = QLabel("Plano: ninguno")
        self.floor_plan_label.setWordWrap(True)
        sidebar.addWidget(self.floor_plan_label)

        self.coverage_label = QLabel("")
        self.coverage_label.setWordWrap(True)
        sidebar.addWidget(self.coverage_label)

        manual = QFormLayout()
        self.manual_x = QDoubleSpinBox()
        self.manual_y = QDoubleSpinBox()
        manual.addRow("X:", self.manual_x)
        manual.addRow("Y:", self.manual_y)
        sidebar.addLayout(manual)
        add_manual = QPushButton("Añadir coordenadas")
        add_manual.clicked.connect(
            lambda: self.registrar_medicion_en(self.manual_x.value(), self.manual_y.value())
        )
        sidebar.addWidget(add_manual)
        sidebar.addStretch()

        self.canvas = LienzoMapaCalor(self)
        layout.addWidget(self.canvas, stretch=1)

        self.x_spin.valueChanged.connect(self.area_cambiada)
        self.y_spin.valueChanged.connect(self.area_cambiada)
        self.ssid_combo.currentTextChanged.connect(lambda: self.canvas.redraw())

        self._survey_timer = QTimer(self)
        self._survey_timer.timeout.connect(self.tick_recorrido)

        self.actualizar_plantas()
        self.sincronizar_desde_planta()

    def actualizar_plantas(self) -> None:
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for f in self.session.floors:
            self.floor_combo.addItem(f.name, f.id)
        idx = max(0, self.floor_combo.findData(self.session.planta_activa_id))
        self.floor_combo.setCurrentIndex(idx)
        self.floor_combo.blockSignals(False)

    def sincronizar_desde_planta(self) -> None:
        floor = self.session.planta_activa
        self.x_spin.setValue(floor.x_max)
        self.y_spin.setValue(floor.y_max)
        if floor.floor_plan_path:
            from pathlib import Path
            self.floor_plan_label.setText(f"Plano: {Path(floor.floor_plan_path).name}")
        else:
            self.floor_plan_label.setText("Plano: ninguno")
        self.canvas.redraw()

    def cambiar_planta(self, index: int) -> None:
        fid = self.floor_combo.itemData(index)
        if fid:
            self.session.planta_activa_id = fid
            self.sincronizar_desde_planta()
            self.planta_cambiada.emit()

    def anadir_planta_ui(self) -> None:
        name, ok = QInputDialog.getText(self, "Nuevo piso", "Nombre:")
        if ok and name.strip():
            self.session.anadir_planta(name.strip())
            self.actualizar_plantas()
            self.sincronizar_desde_planta()
            self.planta_cambiada.emit()

    def renombrar_planta(self) -> None:
        floor = self.session.planta_activa
        name, ok = QInputDialog.getText(self, "Renombrar", "Nombre:", text=floor.name)
        if ok and name.strip():
            floor.name = name.strip()
            self.session.touch()
            self.actualizar_plantas()

    def area_cambiada(self) -> None:
        floor = self.session.planta_activa
        floor.x_max = self.x_spin.value()
        floor.y_max = self.y_spin.value()
        self.manual_x.setMaximum(floor.x_max)
        self.manual_y.setMaximum(floor.y_max)
        self.session.touch()
        self.canvas.redraw()

    def establecer_redes(self, networks) -> None:
        self._networks = networks
        current = self.ssid_combo.currentText()
        self.ssid_combo.blockSignals(True)
        self.ssid_combo.clear()
        ssids = sorted({n.ssid for n in networks if n.ssid})
        self.ssid_combo.addItems(ssids)
        if current in ssids:
            self.ssid_combo.setCurrentText(current)
        self.compare_list.clear()
        for s in ssids:
            self.compare_list.addItem(s)
        self.compare_list.itemSelectionChanged.connect(lambda: self.canvas.redraw())
        self.ssid_combo.blockSignals(False)
        self.canvas.redraw()

    def establecer_ssid_objetivo(self, ssid: str) -> None:
        idx = self.ssid_combo.findText(ssid)
        if idx >= 0:
            self.ssid_combo.setCurrentIndex(idx)

    def cargar_plano_planta(self, path: str) -> bool:
        from pathlib import Path
        if not Path(path).is_file():
            return False
        floor = self.session.planta_activa
        floor.floor_plan_path = path
        self.floor_plan_label.setText(f"Plano: {Path(path).name}")
        self.session.touch()
        self.canvas.redraw()
        return True

    def quitar_plano_planta(self) -> None:
        self.session.planta_activa.floor_plan_path = None
        self.floor_plan_label.setText("Plano: ninguno")
        self.session.touch()
        self.canvas.redraw()

    def senal_objetivo(self) -> tuple[int | None, str, str]:
        ssid = self.ssid_combo.currentText()
        if not ssid:
            c = obtener_red_conectada()
            if c:
                return c.signal_dbm, c.ssid, c.bssid
            return None, "", ""
        matches = [n for n in self._networks if n.ssid == ssid]
        if matches:
            best = max(matches, key=lambda n: n.signal_dbm)
            return best.signal_dbm, best.ssid, best.bssid
        c = obtener_red_conectada()
        if c and c.ssid == ssid:
            return c.signal_dbm, c.ssid, c.bssid
        return None, "", ""

    def registrar_medicion_en(self, x: float, y: float) -> None:
        signal, ssid, bssid = self.senal_objetivo()
        if signal is None:
            QMessageBox.warning(self, "Sin señal", "No se detectó la red seleccionada.")
            return
        self.apilar_deshacer()
        m = Medicion(
            x=x, y=y, signal_dbm=signal, ssid=ssid, bssid=bssid,
            floor_id=self.session.planta_activa.id, timestamp=time.time(),
        )
        self.session.planta_activa.measurements.append(m)
        self.session.touch()
        self.canvas.redraw()

    def medir_centro(self) -> None:
        f = self.session.planta_activa
        self.registrar_medicion_en(f.x_max / 2, f.y_max / 2)

    def apilar_deshacer(self) -> None:
        floor = self.session.planta_activa
        self._undo.append([m.a_dict() for m in floor.measurements])
        self._redo.clear()

    def deshacer_accion(self) -> None:
        if not self._undo:
            return
        floor = self.session.planta_activa
        self._redo.append([m.a_dict() for m in floor.measurements])
        data = self._undo.pop()
        floor.measurements = [Medicion.desde_dict(d) for d in data]
        self.canvas.redraw()

    def rehacer_accion(self) -> None:
        if not self._redo:
            return
        floor = self.session.planta_activa
        self._undo.append([m.a_dict() for m in floor.measurements])
        data = self._redo.pop()
        floor.measurements = [Medicion.desde_dict(d) for d in data]
        self.canvas.redraw()

    def limpiar(self) -> None:
        self.apilar_deshacer()
        self.session.planta_activa.measurements.clear()
        self.session.touch()
        self.canvas.redraw()

    def punto_mas_cercano(self, x: float, y: float, threshold: float = 1.0) -> int | None:
        best, best_d = None, threshold
        for i, m in enumerate(self.session.planta_activa.measurements):
            d = ((m.x - x) ** 2 + (m.y - y) ** 2) ** 0.5
            if d < best_d:
                best, best_d = i, d
        return best

    def menu_punto(self, idx: int) -> None:
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("Eliminar", lambda: self.eliminar_punto(idx))
        menu.addAction("Editar nota", lambda: self.editar_nota(idx))
        menu.exec(self.mapToGlobal(self.rect().center()))

    def eliminar_punto(self, idx: int) -> None:
        self.apilar_deshacer()
        del self.session.planta_activa.measurements[idx]
        self.session.touch()
        self.canvas.redraw()

    def editar_nota(self, idx: int) -> None:
        m = self.session.planta_activa.measurements[idx]
        note, ok = QInputDialog.getText(self, "Nota", "Nota:", text=m.notes)
        if ok:
            m.notes = note
            self.session.touch()
            self.canvas.redraw()

    def obstaculo_mas_cercano(self, x: float, y: float, threshold: float = 0.6) -> int | None:
        best, best_d = None, threshold
        for i, obs in enumerate(self.session.planta_activa.obstaculos):
            d = self._distancia_a_segmento(x, y, obs.x1, obs.y1, obs.x2, obs.y2)
            if d < best_d:
                best, best_d = i, d
        return best

    @staticmethod
    def _distancia_a_segmento(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

    def material_pared_cambiado(self) -> None:
        key = self.material_pared_combo.currentData()
        if key and key != "personalizado":
            self.atenuacion_pared_spin.blockSignals(True)
            self.atenuacion_pared_spin.setValue(atenuacion_material(key))
            self.atenuacion_pared_spin.blockSignals(False)

    def atenuacion_pared_cambiada(self) -> None:
        key = self.material_pared_combo.currentData()
        if not key or key == "personalizado":
            return
        preset = atenuacion_material(key)
        if abs(self.atenuacion_pared_spin.value() - preset) > 0.01:
            idx = self.material_pared_combo.findData("personalizado")
            if idx >= 0:
                self.material_pared_combo.blockSignals(True)
                self.material_pared_combo.setCurrentIndex(idx)
                self.material_pared_combo.blockSignals(False)

    def menu_obstaculo(self, idx: int) -> None:
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction("Editar pared…", lambda: self.editar_obstaculo(idx))
        menu.addAction("Eliminar", lambda: self.eliminar_obstaculo(idx))
        menu.exec(self.mapToGlobal(self.rect().center()))

    def editar_obstaculo(self, idx: int) -> None:
        obs = self.session.planta_activa.obstaculos[idx]
        dlg = DialogoEditarPared(obs, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        material, att = dlg.resultado()
        obs.material = material
        obs.atenuacion_db = att
        self.session.touch()
        self.canvas.redraw()

    def eliminar_obstaculo(self, idx: int) -> None:
        del self.session.planta_activa.obstaculos[idx]
        self.session.touch()
        self.canvas.redraw()

    def alternar_modo_pared(self, on: bool) -> None:
        self.modo_pared = on
        if on:
            self.calibrate_mode = False
            self.calibrate_btn.setChecked(False)
            if self.survey_btn.isChecked():
                self.survey_btn.setChecked(False)
            QMessageBox.information(
                self,
                "Paredes",
                "Arrastra sobre el plano para dibujar una pared (vista previa en tiempo real).\n"
                "Clic derecho sobre una pared para editarla o eliminarla.\n\n"
                "Ajusta el material o la atenuación (dB) antes de dibujar.\n"
                "La interpolación restará la atenuación cuando el rayo "
                "medición→píxel cruce la pared.",
            )
        else:
            self.canvas._wall_start = None
            self.canvas._limpiar_preview_pared()
            self.canvas.draw_idle()

    def limpiar_paredes(self) -> None:
        floor = self.session.planta_activa
        if not floor.obstaculos:
            return
        floor.obstaculos.clear()
        self.session.touch()
        self.canvas.redraw()

    def alternar_calibrar(self, on: bool) -> None:
        self.calibrate_mode = on
        if on:
            self.modo_pared = False
            self.modo_pared_btn.setChecked(False)
            QMessageBox.information(
                self, "Calibración",
                "Dibuja una línea sobre una distancia conocida del plano.",
            )

    def alternar_recorrido(self, on: bool) -> None:
        if on:
            self.survey.iniciar_recorrido_auto(
                self.session.planta_activa.x_max / 2,
                self.manual_y.value(),
            )
            self._survey_timer.start(self.prefs.survey_interval_sec * 1000)
            self.survey_btn.setText("Detener recorrido")
        else:
            self.survey.stop()
            self._survey_timer.stop()
            self.survey_btn.setText("Iniciar recorrido auto")

    def tick_recorrido(self) -> None:
        pos = self.survey.tick()
        if pos:
            self.registrar_medicion_en(pos[0], pos[1])

    def registrar_punto_ruta(self) -> None:
        unreg = [w for w in self.session.planta_activa.waypoints if not w.registered]
        if not unreg:
            QMessageBox.information(self, "PuntoRutas", "Añade waypoints con Shift+clic.")
            return
        wp = unreg[0]
        signal, _, _ = self.senal_objetivo()
        if signal is None:
            return
        wp.registered = True
        wp.signal_dbm = signal
        self.session.touch()
        self.canvas.redraw()

    def actualizar_cobertura(self) -> None:
        from wifind.mapa_calor import interpolar_senal
        floor = self.session.planta_activa
        if not floor.measurements:
            self.coverage_label.setText("")
            return
        _, _, grid_z = interpolar_senal(
            floor.measurements,
            x_max=floor.x_max,
            y_max=floor.y_max,
            obstaculos=floor.obstaculos or None,
        )
        stats = calcular_estadisticas_cobertura(grid_z, floor.x_max, floor.y_max, self.prefs.threshold_fair)
        self.coverage_label.setText(
            f"Cobertura buena: {stats.porcentaje_bueno:.0f}% | Débil: {stats.porcentaje_debil:.0f}%"
        )
