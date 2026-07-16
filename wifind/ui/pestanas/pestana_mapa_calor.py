"""Pestaña mapa de calor."""

from __future__ import annotations

import time

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wifind.mapa_calor import (
    color_material,
    dibujar_mapa_calor_comparacion_en,
    dibujar_mapa_calor_en,
)
from wifind.modelos.medicion import (
    COLORES_HABITACION,
    MATERIALES_PARED,
    Medicion,
    Habitacion,
    NOMBRES_HABITACION,
    Obstaculo,
    PuntoAcceso,
    PuntoRuta,
    TIPOS_PUNTO_ACCESO,
    atenuacion_material,
    nombre_por_defecto_ap,
)
from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import SesionApp, NivelPlanta
from wifind.servicios.cobertura import calcular_estadisticas_cobertura
from wifind.servicios.escala_plano import (
    calcular_metricas_escala,
    distancia_metros,
    esta_calibrado,
    formatear_area,
    formatear_longitud,
    metros_a_px,
)
from wifind.servicios.habitaciones import evaluar_habitaciones_planta
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


class DialogoEditarAP(QDialog):
    def __init__(self, ap: PuntoAcceso, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar punto de acceso")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.tipo_combo = QComboBox()
        for key, (label, _, _) in TIPOS_PUNTO_ACCESO.items():
            self.tipo_combo.addItem(f"📡 {label}", key)
        idx = max(0, self.tipo_combo.findData(ap.tipo))
        self.tipo_combo.setCurrentIndex(idx)
        self.nombre_edit = QLineEdit(ap.nombre)
        form.addRow("Tipo:", self.tipo_combo)
        form.addRow("Nombre:", self.nombre_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def resultado(self) -> tuple[str, str]:
        return self.tipo_combo.currentData(), self.nombre_edit.text().strip() or "AP"


class DialogoEditarHabitacion(QDialog):
    def __init__(self, habitacion: Habitacion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar habitación")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.nombre_combo = QComboBox()
        self.nombre_combo.setEditable(True)
        for nombre in NOMBRES_HABITACION:
            self.nombre_combo.addItem(nombre)
        self.nombre_combo.setCurrentText(habitacion.nombre)
        form.addRow("Nombre:", self.nombre_combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def resultado(self) -> str:
        return self.nombre_combo.currentText().strip() or "Habitación"


class LienzoMapaCalor(FigureCanvasQTAgg):
    def __init__(self, tab: "PestanaMapaCalor", parent=None) -> None:
        self.tab = tab
        self._drag_idx: int | None = None
        self._drag_ap_idx: int | None = None
        self._ap_drag_marker = None
        self._ap_drag_label = None
        self._cal_start: tuple[float, float] | None = None
        self._wall_start: tuple[float, float] | None = None
        self._measure_start: tuple[float, float] | None = None
        self._room_start: tuple[float, float] | None = None
        self._wall_preview_line = None
        self._measure_preview_line = None
        self._room_preview_patch = None
        figure = Figure(figsize=(6, 5), dpi=100)
        super().__init__(figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("motion_notify_event", self._on_motion)

    def redraw(self) -> None:
        self._limpiar_preview_pared()
        self._limpiar_preview_habitacion()
        floor = self.tab.session.planta_activa
        prefs = self.tab.prefs
        cal = floor.calibration
        cal_line = None
        if cal.real_length_m > 0:
            cal_line = (cal.x1, cal.y1, cal.x2, cal.y2)

        fig = self.figure
        fig.clear()

        etiquetas = self.tab.etiquetas_habitaciones()

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
                floor.access_points,
                floor.habitaciones,
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
                floor.access_points,
                floor.habitaciones,
                etiquetas,
                self.tab.router_para_cobertura(),
                self.tab.radios_router_para_dibujo(),
                floor.calibration if self.tab.mostrar_cobertura_router else None,
                prefs.sufijo_longitud(),
                theme=prefs.theme,
            )
            self._dibujar_radios_cobertura(ax, pts, floor.calibration)

        self.draw_idle()
        self.tab.actualizar_cobertura()
        self.tab.actualizar_etiqueta_escala()

    def _dibujar_radios_cobertura(self, ax, pts, cal) -> None:
        if not self.tab.mostrar_radio or not esta_calibrado(cal):
            return
        radio_px = metros_a_px(self.tab.radio_cobertura_m, cal)
        if radio_px is None or radio_px <= 0 or not pts:
            return
        for p in pts:
            circ = Circle(
                (p.x, p.y),
                radio_px,
                fill=False,
                edgecolor="#1565C0",
                linewidth=1.2,
                linestyle="--",
                alpha=0.65,
                zorder=4,
            )
            ax.add_patch(circ)

    def _limpiar_preview_pared(self) -> None:
        if self._wall_preview_line is not None:
            try:
                self._wall_preview_line.remove()
            except (ValueError, AttributeError):
                pass
            self._wall_preview_line = None

    def _limpiar_preview_medida(self) -> None:
        if self._measure_preview_line is not None:
            try:
                self._measure_preview_line.remove()
            except (ValueError, AttributeError):
                pass
            self._measure_preview_line = None

    def _limpiar_preview_habitacion(self) -> None:
        if self._room_preview_patch is not None:
            try:
                self._room_preview_patch.remove()
            except (ValueError, AttributeError):
                pass
            self._room_preview_patch = None

    def _limpiar_preview_drag_ap(self) -> None:
        for attr in ("_ap_drag_marker", "_ap_drag_label"):
            artist = getattr(self, attr, None)
            if artist is not None:
                try:
                    artist.remove()
                except (ValueError, AttributeError):
                    pass
                setattr(self, attr, None)

    def _actualizar_preview_drag_ap(self, x: float, y: float) -> None:
        from wifind.modelos.medicion import color_tipo_ap, marcador_tipo_ap

        ap = self.tab.session.planta_activa.access_points[self._drag_ap_idx]
        color = color_tipo_ap(ap.tipo)
        ax = self.figure.gca()
        if self._ap_drag_marker is None:
            (self._ap_drag_marker,) = ax.plot(
                [x],
                [y],
                marker=marcador_tipo_ap(ap.tipo),
                markersize=14,
                color=color,
                markeredgecolor="white",
                markeredgewidth=1.2,
                linestyle="None",
                zorder=20,
            )
            self._ap_drag_label = ax.annotate(
                ap.nombre + (" *" if ap.es_referencia else ""),
                (x, y),
                textcoords="offset points",
                xytext=(0, 12),
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color=color,
                zorder=21,
            )
        else:
            self._ap_drag_marker.set_data([x], [y])
            self._ap_drag_label.xy = (x, y)
        self.draw_idle()

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

    def _actualizar_preview_medida(self, x2: float, y2: float) -> None:
        if self._measure_start is None:
            return
        x1, y1 = self._measure_start
        ax = self.figure.gca()
        if self._measure_preview_line is None:
            (self._measure_preview_line,) = ax.plot(
                [x1, x2],
                [y1, y2],
                color="#FF6F00",
                linewidth=2.5,
                linestyle="-",
                alpha=0.9,
                zorder=11,
            )
        else:
            self._measure_preview_line.set_data([x1, x2], [y1, y2])
        dist_m = distancia_metros(x1, y1, x2, y2, self.tab.session.planta_activa.calibration)
        texto = formatear_longitud(dist_m, self.tab.prefs.units)
        self.tab.measure_result_label.setText(f"Distancia: {texto}")
        self.draw_idle()

    def _actualizar_preview_habitacion(self, x2: float, y2: float) -> None:
        if self._room_start is None:
            return
        from matplotlib.patches import Rectangle

        x1, y1 = self._room_start
        xa, ya = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        ax = self.figure.gca()
        color = self.tab.color_habitacion_actual()
        if self._room_preview_patch is None:
            self._room_preview_patch = Rectangle(
                (xa, ya),
                w,
                h,
                fill=True,
                facecolor=color,
                edgecolor=color,
                linewidth=1.8,
                linestyle="--",
                alpha=0.25,
                zorder=12,
            )
            ax.add_patch(self._room_preview_patch)
        else:
            self._room_preview_patch.set_xy((xa, ya))
            self._room_preview_patch.set_width(w)
            self._room_preview_patch.set_height(h)
            self._room_preview_patch.set_facecolor(color)
            self._room_preview_patch.set_edgecolor(color)
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

        if self.tab.measure_mode:
            if event.button == 1:
                self._measure_start = (x, y)
            return

        if self.tab.modo_pared:
            if event.button == 1:
                self._wall_start = (x, y)
            return

        if self.tab.modo_habitacion:
            if event.button == 1:
                self._room_start = (x, y)
            return

        if self.tab.modo_ap:
            if event.button == 1:
                # Si hay un AP cerca, arrastrarlo; si no, colocar uno nuevo
                ap_idx = self.tab.ap_mas_cercano(x, y)
                if ap_idx is not None:
                    self._drag_ap_idx = ap_idx
                else:
                    self.tab.colocar_ap_en(x, y)
            return

        if event.key == "shift" and event.button == 1:
            floor.waypoints.append(PuntoRuta(x=x, y=y))
            self.tab.session.touch()
            self.redraw()
            return

        if event.button == 3:
            room_idx = self.tab.habitacion_en_punto(x, y)
            if room_idx is not None:
                self.tab.menu_habitacion(room_idx)
                return
            ap_idx = self.tab.ap_mas_cercano(x, y)
            if ap_idx is not None:
                self.tab.menu_ap(ap_idx)
                return
            wall_idx = self.tab.obstaculo_mas_cercano(x, y)
            if wall_idx is not None:
                self.tab.menu_obstaculo(wall_idx)
                return
            idx = self.tab.punto_mas_cercano(x, y)
            if idx is not None:
                self.tab.menu_punto(idx)
            return

        if event.button == 1:
            ap_idx = self.tab.ap_mas_cercano(x, y)
            if ap_idx is not None:
                self._drag_ap_idx = ap_idx
                return
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
            unidad = "ft" if self.tab.prefs.units == "ft" else "m"
            length, ok = QInputDialog.getDouble(
                self.tab,
                "Calibración",
                f"Longitud real de la línea ({unidad}):\nEjemplo: 8 {unidad}",
                8.0 if unidad == "m" else 26.0,
                0.01,
                1000,
                2,
            )
            if ok and length > 0:
                import math

                length_m = self.tab.prefs.a_metros(length)
                pixel_dist = math.hypot(x2 - x1, y2 - y1)
                cal = self.tab.session.planta_activa.calibration
                cal.x1, cal.y1, cal.x2, cal.y2 = x1, y1, x2, y2
                cal.real_length_m = length_m
                cal.pixels_per_meter = pixel_dist / length_m if length_m else 0
                self.tab.calibrate_mode = False
                self.tab.calibrate_btn.setChecked(False)
                self.tab.session.touch()
            self._cal_start = None
            self.redraw()
            return

        if self.tab.measure_mode and self._measure_start and event.button == 1:
            if event.xdata is None or event.ydata is None:
                self._measure_start = None
                self._limpiar_preview_medida()
                return
            x1, y1 = self._measure_start
            x2, y2 = event.xdata, event.ydata
            dist_m = distancia_metros(
                x1, y1, x2, y2, self.tab.session.planta_activa.calibration
            )
            self.tab.measure_result_label.setText(
                f"Distancia: {formatear_longitud(dist_m, self.tab.prefs.units)}"
            )
            # Dejar la línea medida visible hasta el siguiente redraw
            ax = self.figure.gca()
            ax.plot([x1, x2], [y1, y2], color="#FF6F00", linewidth=2.5, zorder=11)
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(
                mid_x,
                mid_y,
                formatear_longitud(dist_m, self.tab.prefs.units),
                color="#E65100",
                fontsize=10,
                fontweight="bold",
                ha="center",
                va="bottom",
                zorder=12,
            )
            self._limpiar_preview_medida()
            self._measure_start = None
            self.draw_idle()
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

        if self.tab.modo_habitacion and self._room_start and event.button == 1:
            self._limpiar_preview_habitacion()
            if event.xdata is None or event.ydata is None:
                self._room_start = None
                return
            x1, y1 = self._room_start
            x2, y2 = event.xdata, event.ydata
            import math

            if math.hypot(x2 - x1, y2 - y1) >= 0.3:
                self.tab.colocar_habitacion_rect(x1, y1, x2, y2)
            self._room_start = None
            self.redraw()
            return

        if self._drag_ap_idx is not None:
            self._limpiar_preview_drag_ap()
            self.tab.session.touch()
            self._drag_ap_idx = None
            self.redraw()
            return

        self._drag_idx = None

    def _on_motion(self, event) -> None:
        if (
            self.tab.measure_mode
            and self._measure_start is not None
            and event.xdata is not None
            and event.ydata is not None
        ):
            self._actualizar_preview_medida(event.xdata, event.ydata)
            return
        if (
            self.tab.modo_pared
            and self._wall_start is not None
            and event.xdata is not None
            and event.ydata is not None
        ):
            self._actualizar_preview_pared(event.xdata, event.ydata)
            return
        if (
            self.tab.modo_habitacion
            and self._room_start is not None
            and event.xdata is not None
            and event.ydata is not None
        ):
            self._actualizar_preview_habitacion(event.xdata, event.ydata)
            return
        if self._drag_ap_idx is not None and event.xdata is not None and event.ydata is not None:
            ap = self.tab.session.planta_activa.access_points[self._drag_ap_idx]
            ap.x = event.xdata
            ap.y = event.ydata
            self._actualizar_preview_drag_ap(event.xdata, event.ydata)
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
        self.measure_mode = False
        self.mostrar_radio = False
        self.mostrar_cobertura_router = False
        self.radio_cobertura_m = 5.0
        self.modo_pared = False
        self.modo_ap = False
        self.modo_habitacion = False
        self._undo: list[list] = []
        self._redo: list[list] = []

        self.survey = MotorRecorrido(
            interval_sec=prefs.survey_interval_sec,
            step_y=prefs.walk_step_m,
            advance_y=prefs.auto_survey_advance_y,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        sidebar_host = QWidget()
        sidebar = QVBoxLayout(sidebar_host)
        sidebar.setContentsMargins(4, 4, 8, 4)
        sidebar.setSpacing(4)

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

        self.scale_label = QLabel("Escala: sin calibrar")
        self.scale_label.setWordWrap(True)
        sidebar.addWidget(self.scale_label)

        self.measure_dist_btn = QPushButton("Medir distancia")
        self.measure_dist_btn.setCheckable(True)
        self.measure_dist_btn.toggled.connect(self.alternar_medir_distancia)
        sidebar.addWidget(self.measure_dist_btn)

        self.measure_result_label = QLabel("Distancia: —")
        self.measure_result_label.setWordWrap(True)
        sidebar.addWidget(self.measure_result_label)

        self.radius_check = QCheckBox("Mostrar radio de cobertura")
        self.radius_check.toggled.connect(self.alternar_radio_cobertura)
        sidebar.addWidget(self.radius_check)

        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.5, 100.0)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setSingleStep(0.5)
        self.radius_spin.setValue(self.prefs.desde_metros(5.0))
        self.radius_spin.setSuffix(self.prefs.sufijo_longitud())
        self.radius_spin.valueChanged.connect(self.radio_cobertura_cambiado)
        sidebar.addWidget(self.radius_spin)

        self.router_coverage_check = QCheckBox("Cobertura respecto al router")
        self.router_coverage_check.toggled.connect(self.alternar_cobertura_router)
        sidebar.addWidget(self.router_coverage_check)

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

        self.modo_habitacion_btn = QPushButton("Dibujar habitaciones")
        self.modo_habitacion_btn.setCheckable(True)
        self.modo_habitacion_btn.toggled.connect(self.alternar_modo_habitacion)
        sidebar.addWidget(self.modo_habitacion_btn)

        self.nombre_habitacion_combo = QComboBox()
        self.nombre_habitacion_combo.setEditable(True)
        for nombre in NOMBRES_HABITACION:
            self.nombre_habitacion_combo.addItem(nombre)
        self.nombre_habitacion_combo.setCurrentText("Salón")
        sidebar.addWidget(QLabel("Nombre habitación:"))
        sidebar.addWidget(self.nombre_habitacion_combo)

        self.limpiar_habitaciones_btn = QPushButton("Limpiar habitaciones")
        self.limpiar_habitaciones_btn.clicked.connect(self.limpiar_habitaciones)
        sidebar.addWidget(self.limpiar_habitaciones_btn)

        self.rooms_label = QLabel("")
        self.rooms_label.setWordWrap(True)
        sidebar.addWidget(self.rooms_label)

        self.modo_ap_btn = QPushButton("Colocar AP")
        self.modo_ap_btn.setCheckable(True)
        self.modo_ap_btn.toggled.connect(self.alternar_modo_ap)
        sidebar.addWidget(self.modo_ap_btn)

        self.tipo_ap_combo = QComboBox()
        for key, (label, _, _) in TIPOS_PUNTO_ACCESO.items():
            self.tipo_ap_combo.addItem(f"📡 {label}", key)
        self.tipo_ap_combo.setCurrentIndex(self.tipo_ap_combo.findData("ap"))
        self.tipo_ap_combo.currentIndexChanged.connect(self.tipo_ap_cambiado)
        sidebar.addWidget(QLabel("Tipo de equipo:"))
        sidebar.addWidget(self.tipo_ap_combo)

        self.nombre_ap_edit = QLineEdit(nombre_por_defecto_ap("ap"))
        self.nombre_ap_edit.setPlaceholderText("Nombre en el plano")
        sidebar.addWidget(QLabel("Nombre:"))
        sidebar.addWidget(self.nombre_ap_edit)

        self.limpiar_aps_btn = QPushButton("Limpiar APs")
        self.limpiar_aps_btn.clicked.connect(self.limpiar_aps)
        sidebar.addWidget(self.limpiar_aps_btn)

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

        scroll = QScrollArea()
        scroll.setWidget(sidebar_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(250)
        scroll.setMaximumWidth(340)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(scroll, stretch=0)

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
        self.actualizar_etiqueta_escala()
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
            self.measure_mode = False
            self.measure_dist_btn.setChecked(False)
            self.modo_ap = False
            self.modo_ap_btn.setChecked(False)
            self.modo_habitacion = False
            self.modo_habitacion_btn.setChecked(False)
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

    def alternar_modo_ap(self, on: bool) -> None:
        self.modo_ap = on
        if on:
            self.calibrate_mode = False
            self.calibrate_btn.setChecked(False)
            self.measure_mode = False
            self.measure_dist_btn.setChecked(False)
            self.modo_pared = False
            self.modo_pared_btn.setChecked(False)
            self.modo_habitacion = False
            self.modo_habitacion_btn.setChecked(False)
            if self.survey_btn.isChecked():
                self.survey_btn.setChecked(False)
            QMessageBox.information(
                self,
                "Colocar AP",
                "Elige el tipo (Router, AP, Repetidor) y un nombre,\n"
                "luego haz clic en el plano para colocarlo.\n\n"
                "Clic derecho sobre un AP: editar, marcar como referencia o eliminar.\n"
                "Arrastra un AP (incluido el router) para moverlo.",
            )

    def color_habitacion_actual(self) -> str:
        n = len(self.session.planta_activa.habitaciones)
        return COLORES_HABITACION[n % len(COLORES_HABITACION)]

    def alternar_modo_habitacion(self, on: bool) -> None:
        self.modo_habitacion = on
        if on:
            self.calibrate_mode = False
            self.calibrate_btn.setChecked(False)
            self.measure_mode = False
            self.measure_dist_btn.setChecked(False)
            self.modo_pared = False
            self.modo_pared_btn.setChecked(False)
            self.modo_ap = False
            self.modo_ap_btn.setChecked(False)
            if self.survey_btn.isChecked():
                self.survey_btn.setChecked(False)
            QMessageBox.information(
                self,
                "Habitaciones",
                "Elige un nombre (Salón, Dormitorio, Cocina…)\n"
                "y arrastra un rectángulo sobre el plano.\n\n"
                "Con mediciones, cada habitación se evalúa como\n"
                "Excelente / Buena / Aceptable / Deficiente.\n"
                "Clic derecho: editar o eliminar.",
            )
        else:
            self.canvas._room_start = None
            self.canvas._limpiar_preview_habitacion()
            self.canvas.draw_idle()

    def colocar_habitacion_rect(self, x1: float, y1: float, x2: float, y2: float) -> None:
        nombre = self.nombre_habitacion_combo.currentText().strip() or "Habitación"
        hab = Habitacion.desde_rectangulo(
            x1, y1, x2, y2, nombre, self.color_habitacion_actual()
        )
        self.session.planta_activa.habitaciones.append(hab)
        self.session.touch()
        # Avanzar al siguiente nombre sugerido
        idx = self.nombre_habitacion_combo.currentIndex()
        if 0 <= idx < self.nombre_habitacion_combo.count() - 1:
            self.nombre_habitacion_combo.setCurrentIndex(idx + 1)

    def habitacion_en_punto(self, x: float, y: float) -> int | None:
        from matplotlib.path import Path

        # La más pequeña que contenga el punto (prioridad a habitaciones internas)
        candidatos: list[tuple[float, int]] = []
        for i, hab in enumerate(self.session.planta_activa.habitaciones):
            if len(hab.vertices) < 3:
                continue
            if Path(hab.vertices).contains_point((x, y)):
                xs = [v[0] for v in hab.vertices]
                ys = [v[1] for v in hab.vertices]
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                candidatos.append((area, i))
        if not candidatos:
            return None
        candidatos.sort()
        return candidatos[0][1]

    def menu_habitacion(self, idx: int) -> None:
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction("Editar habitación…", lambda: self.editar_habitacion(idx))
        menu.addAction("Eliminar", lambda: self.eliminar_habitacion(idx))
        menu.exec(self.mapToGlobal(self.rect().center()))

    def editar_habitacion(self, idx: int) -> None:
        hab = self.session.planta_activa.habitaciones[idx]
        dlg = DialogoEditarHabitacion(hab, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        hab.nombre = dlg.resultado()
        self.session.touch()
        self.canvas.redraw()

    def eliminar_habitacion(self, idx: int) -> None:
        del self.session.planta_activa.habitaciones[idx]
        self.session.touch()
        self.canvas.redraw()

    def limpiar_habitaciones(self) -> None:
        floor = self.session.planta_activa
        if not floor.habitaciones:
            return
        floor.habitaciones.clear()
        self.session.touch()
        self.canvas.redraw()

    def etiquetas_habitaciones(self) -> dict[str, str]:
        floor = self.session.planta_activa
        if not floor.habitaciones or not floor.measurements:
            return {}
        from wifind.mapa_calor import interpolar_senal

        ssid = self.ssid_combo.currentText()
        pts = floor.measurements
        if ssid:
            pts = [m for m in pts if not m.ssid or m.ssid == ssid]
        if not pts:
            return {}
        grid_x, grid_y, grid_z = interpolar_senal(
            pts,
            x_max=floor.x_max,
            y_max=floor.y_max,
            obstaculos=floor.obstaculos or None,
        )
        evals = evaluar_habitaciones_planta(floor, grid_x, grid_y, grid_z, self.prefs)
        return {e.habitacion.id: e.etiqueta for e in evals}

    def tipo_ap_cambiado(self) -> None:
        tipo = self.tipo_ap_combo.currentData() or "ap"
        actual = self.nombre_ap_edit.text().strip()
        if not actual or actual in {nombre_por_defecto_ap(t) for t in TIPOS_PUNTO_ACCESO}:
            self.nombre_ap_edit.setText(nombre_por_defecto_ap(tipo))

    def colocar_ap_en(self, x: float, y: float) -> None:
        tipo = self.tipo_ap_combo.currentData() or "ap"
        nombre = self.nombre_ap_edit.text().strip() or nombre_por_defecto_ap(tipo)
        floor = self.session.planta_activa
        es_ref = False
        if tipo == "router" and not any(a.es_referencia for a in floor.access_points):
            es_ref = True
        floor.access_points.append(
            PuntoAcceso(x=x, y=y, tipo=tipo, nombre=nombre, es_referencia=es_ref)
        )
        self.session.touch()
        # Salir del modo colocar para poder arrastrar de inmediato
        self.modo_ap_btn.setChecked(False)
        if es_ref:
            self.mostrar_cobertura_router = True
            self.router_coverage_check.blockSignals(True)
            self.router_coverage_check.setChecked(True)
            self.router_coverage_check.blockSignals(False)
        self.canvas.redraw()

    def ap_mas_cercano(self, x: float, y: float, threshold: float | None = None) -> int | None:
        floor = self.session.planta_activa
        if threshold is None:
            # Área de agarre ~5 % del lado mayor (mín. 0.6 unidades de plano)
            threshold = max(0.6, max(floor.x_max, floor.y_max) * 0.05)
        best, best_d = None, threshold
        for i, ap in enumerate(floor.access_points):
            d = ((ap.x - x) ** 2 + (ap.y - y) ** 2) ** 0.5
            if d < best_d:
                best, best_d = i, d
        return best

    def menu_ap(self, idx: int) -> None:
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction("Editar AP…", lambda: self.editar_ap(idx))
        menu.addAction(
            "Usar como router de referencia",
            lambda: self.marcar_router_referencia(idx),
        )
        menu.addAction("Eliminar", lambda: self.eliminar_ap(idx))
        menu.exec(self.mapToGlobal(self.rect().center()))

    def marcar_router_referencia(self, idx: int) -> None:
        floor = self.session.planta_activa
        for i, ap in enumerate(floor.access_points):
            ap.es_referencia = i == idx
            if i == idx:
                ap.tipo = "router"
        self.session.touch()
        self.mostrar_cobertura_router = True
        self.router_coverage_check.blockSignals(True)
        self.router_coverage_check.setChecked(True)
        self.router_coverage_check.blockSignals(False)
        self.canvas.redraw()

    def router_para_cobertura(self):
        if not self.mostrar_cobertura_router:
            return None
        from wifind.servicios.narrativa_informe import router_de_referencia

        return router_de_referencia(self.session.planta_activa)

    def radios_router_para_dibujo(self) -> tuple[float, ...] | None:
        if not self.mostrar_cobertura_router or self.router_para_cobertura() is None:
            return None
        base = max(self.radio_cobertura_m, 3.0)
        return (base, base * 2, base * 3)

    def alternar_cobertura_router(self, on: bool) -> None:
        from wifind.servicios.narrativa_informe import router_de_referencia

        if on and router_de_referencia(self.session.planta_activa) is None:
            self.router_coverage_check.blockSignals(True)
            self.router_coverage_check.setChecked(False)
            self.router_coverage_check.blockSignals(False)
            QMessageBox.information(
                self,
                "Cobertura respecto al router",
                "Coloca un Router en el plano (Colocar AP → Router) o marca uno "
                "existente con clic derecho → «Usar como router de referencia».\n\n"
                "Si ya detectaste el gateway en Dispositivos, usa "
                "«Colocar router en el mapa» allí.",
            )
            return
        self.mostrar_cobertura_router = on
        self.canvas.redraw()

    def iniciar_colocacion_router(self, nombre: str = "Router") -> None:
        """Activa el modo colocar AP como router de referencia (desde Dispositivos)."""
        self.modo_ap_btn.setChecked(True)
        idx = self.tipo_ap_combo.findData("router")
        if idx >= 0:
            self.tipo_ap_combo.setCurrentIndex(idx)
        self.nombre_ap_edit.setText(nombre or "Router")
        QMessageBox.information(
            self,
            "Colocar router",
            f"Haz clic en el plano donde está «{nombre or 'Router'}».\n"
            "Quedará marcado como referencia para la cobertura.",
        )

    def editar_ap(self, idx: int) -> None:
        ap = self.session.planta_activa.access_points[idx]
        dlg = DialogoEditarAP(ap, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        tipo, nombre = dlg.resultado()
        ap.tipo = tipo
        ap.nombre = nombre
        self.session.touch()
        self.canvas.redraw()

    def eliminar_ap(self, idx: int) -> None:
        del self.session.planta_activa.access_points[idx]
        self.session.touch()
        self.canvas.redraw()

    def limpiar_aps(self) -> None:
        floor = self.session.planta_activa
        if not floor.access_points:
            return
        floor.access_points.clear()
        self.session.touch()
        self.canvas.redraw()

    def alternar_calibrar(self, on: bool) -> None:
        self.calibrate_mode = on
        if on:
            self.modo_pared = False
            self.modo_pared_btn.setChecked(False)
            self.measure_mode = False
            self.measure_dist_btn.setChecked(False)
            self.modo_ap = False
            self.modo_ap_btn.setChecked(False)
            self.modo_habitacion = False
            self.modo_habitacion_btn.setChecked(False)
            QMessageBox.information(
                self,
                "Calibración",
                "Dibuja una línea sobre una distancia conocida del plano "
                "(por ejemplo un pasillo de 8 metros) e indica su longitud real.",
            )

    def alternar_medir_distancia(self, on: bool) -> None:
        if on and not esta_calibrado(self.session.planta_activa.calibration):
            self.measure_dist_btn.blockSignals(True)
            self.measure_dist_btn.setChecked(False)
            self.measure_dist_btn.blockSignals(False)
            QMessageBox.information(
                self,
                "Medir distancia",
                "Primero calibra el plano: dibuja una línea sobre una distancia "
                "conocida (ej. 8 m) con «Calibrar plano».",
            )
            return
        self.measure_mode = on
        if on:
            self.calibrate_mode = False
            self.calibrate_btn.setChecked(False)
            self.modo_pared = False
            self.modo_pared_btn.setChecked(False)
            self.modo_ap = False
            self.modo_ap_btn.setChecked(False)
            self.modo_habitacion = False
            self.modo_habitacion_btn.setChecked(False)
            self.measure_result_label.setText("Distancia: arrastra una línea…")
        else:
            self.canvas._measure_start = None
            self.canvas._limpiar_preview_medida()
            self.canvas.draw_idle()

    def alternar_radio_cobertura(self, on: bool) -> None:
        if on and not esta_calibrado(self.session.planta_activa.calibration):
            self.radius_check.blockSignals(True)
            self.radius_check.setChecked(False)
            self.radius_check.blockSignals(False)
            QMessageBox.information(
                self,
                "Radio de cobertura",
                "Calibra el plano primero para mostrar radios en metros reales.",
            )
            return
        self.mostrar_radio = on
        self.canvas.redraw()

    def radio_cobertura_cambiado(self, value: float) -> None:
        self.radio_cobertura_m = self.prefs.a_metros(float(value))
        if self.mostrar_radio:
            self.canvas.redraw()

    def actualizar_etiqueta_escala(self) -> None:
        floor = self.session.planta_activa
        cal = floor.calibration
        if not esta_calibrado(cal):
            self.scale_label.setText("Escala: sin calibrar")
            self.measure_dist_btn.setEnabled(True)
            return
        largo = formatear_longitud(cal.real_length_m, self.prefs.units)
        metricas = calcular_metricas_escala(floor)
        ancho = formatear_longitud(metricas.ancho_m, self.prefs.units)
        alto = formatear_longitud(metricas.alto_m, self.prefs.units)
        self.scale_label.setText(
            f"Escala: {largo} de referencia\n"
            f"Planta ≈ {ancho} × {alto}"
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
            self.rooms_label.setText("")
            return
        grid_x, grid_y, grid_z = interpolar_senal(
            floor.measurements,
            x_max=floor.x_max,
            y_max=floor.y_max,
            obstaculos=floor.obstaculos or None,
        )
        stats = calcular_estadisticas_cobertura(
            grid_z, floor.x_max, floor.y_max, self.prefs.threshold_fair
        )
        metricas = calcular_metricas_escala(floor, stats)
        unidades = self.prefs.units
        lineas = [
            f"Cobertura buena: {stats.porcentaje_bueno:.0f}% | "
            f"Débil: {stats.porcentaje_debil:.0f}%"
        ]
        if metricas.calibrado:
            lineas.append(
                f"Superficie: {formatear_area(metricas.area_total_m2, unidades)}"
            )
            lineas.append(
                f"Buena ≈ {formatear_area(metricas.area_buena_m2, unidades)} · "
                f"Débil ≈ {formatear_area(metricas.area_debil_m2, unidades)}"
            )
            if metricas.densidad_puntos_por_m2 is not None:
                dens = metricas.densidad_puntos_por_m2
                if unidades == "ft":
                    dens_ft = dens * (0.3048 ** 2)
                    lineas.append(
                        f"Densidad: {metricas.n_puntos} pts · {dens_ft:.3f} pts/ft²"
                    )
                else:
                    lineas.append(
                        f"Densidad: {metricas.n_puntos} pts · {dens:.3f} pts/m²"
                    )
        else:
            lineas.append("Calibra el plano para ver m² y densidad.")
        self.coverage_label.setText("\n".join(lineas))

        if floor.habitaciones:
            evals = evaluar_habitaciones_planta(
                floor, grid_x, grid_y, grid_z, self.prefs
            )
            room_lines = ["Por habitación:"]
            for ev in evals:
                media = f" ({ev.media_dbm:.0f} dBm)" if ev.media_dbm is not None else ""
                room_lines.append(f"• {ev.habitacion.nombre}: {ev.etiqueta}{media}")
            self.rooms_label.setText("\n".join(room_lines))
        else:
            self.rooms_label.setText("")
