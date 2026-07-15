"""Pestaña intensidad en vivo."""

from __future__ import annotations

import time

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import SesionApp
from wifind.ui.grafico_intensidad import GraficoIntensidadEnVivo
from wifind.ui.indicador_senal import IndicadorSenal
from wifind.wifi.red import RedWifi, nivel_barras_senal
from wifind.wifi.plataforma import obtener_red_conectada


class PestanaIntensidad(QWidget):
    alerta_activada = pyqtSignal(str)

    def __init__(self, session: SesionApp, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.prefs = prefs
        self._networks: list[RedWifi] = []
        self._monitor_start = time.monotonic()
        self._below_since: float | None = None

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Red a monitorizar:"))
        self.monitor_combo = QComboBox()
        self.monitor_combo.setMinimumWidth(220)
        controls.addWidget(self.monitor_combo)
        self.monitor_btn = QPushButton("Iniciar monitoreo")
        self.monitor_btn.setCheckable(True)
        self.monitor_btn.toggled.connect(self.alternar_monitor)
        controls.addWidget(self.monitor_btn)
        self.clear_btn = QPushButton("Limpiar histórico")
        self.clear_btn.clicked.connect(self.limpiar)
        controls.addWidget(self.clear_btn)
        controls.addStretch()
        layout.addLayout(controls)

        signal_row = QHBoxLayout()
        signal_row.addWidget(QLabel("Intensidad actual:"))
        self.indicador_senal = IndicadorSenal(theme=self.prefs.theme)
        signal_row.addWidget(self.indicador_senal)
        self.live_signal_label = QLabel("— dBm")
        signal_row.addWidget(self.live_signal_label)
        signal_row.addStretch()
        layout.addLayout(signal_row)

        self.alert_label = QLabel("")
        self.alert_label.setStyleSheet("color: #F44336; font-weight: bold;")
        layout.addWidget(self.alert_label)

        self.grafico = GraficoIntensidadEnVivo()
        layout.addWidget(self.grafico)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.actualizar)

        self.dibujar()

    def establecer_redes(self, networks: list[RedWifi]) -> None:
        self._networks = networks
        current = self.monitor_combo.currentText()
        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        ssids = sorted({n.ssid for n in networks if n.ssid})
        self.monitor_combo.addItems(ssids)
        if current in ssids:
            self.monitor_combo.setCurrentText(current)
        elif ssids:
            self.monitor_combo.setCurrentIndex(0)
        self.monitor_combo.blockSignals(False)

    def establecer_ssid_monitor(self, ssid: str) -> None:
        idx = self.monitor_combo.findText(ssid)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)

    def alternar_monitor(self, active: bool) -> None:
        if active:
            ssid = self.monitor_combo.currentText()
            if not ssid:
                QMessageBox.information(self, "WiFind", "Selecciona una red.")
                self.monitor_btn.setChecked(False)
                return
            self.session.intensity.ssid = ssid
            self._monitor_start = time.monotonic()
            self.session.intensity.timestamps.clear()
            self.session.intensity.values_dbm.clear()
            self.monitor_btn.setText("Detener monitoreo")
            self._timer.start()
            self.actualizar()
        else:
            self.monitor_btn.setText("Iniciar monitoreo")
            self._timer.stop()
            self.alert_label.setText("")
            self.indicador_senal.establecer_barras(0)
            self.live_signal_label.setText("— dBm")

    def limpiar(self) -> None:
        self.session.intensity.timestamps.clear()
        self.session.intensity.values_dbm.clear()
        self.dibujar()

    def actualizar(self) -> None:
        ssid = self.monitor_combo.currentText()
        if not ssid:
            return
        matches = [n for n in self._networks if n.ssid == ssid]
        signal = None
        if matches:
            signal = max(matches, key=lambda n: n.signal_dbm).signal_dbm
        else:
            conn = obtener_red_conectada()
            if conn and conn.ssid == ssid:
                signal = conn.signal_dbm
        if signal is None:
            self.indicador_senal.establecer_barras(0)
            self.live_signal_label.setText("— dBm")
            return

        self.indicador_senal.establecer_barras(
            nivel_barras_senal(signal, self.prefs.thresholds),
            signal_dbm=signal,
        )
        self.live_signal_label.setText(f"{signal} dBm")

        elapsed = time.monotonic() - self._monitor_start
        self.session.intensity.timestamps.append(elapsed)
        self.session.intensity.values_dbm.append(signal)
        self.session.touch()

        if signal < self.prefs.alert_threshold_dbm:
            if self._below_since is None:
                self._below_since = time.monotonic()
            elif time.monotonic() - self._below_since >= self.prefs.alert_duration_sec:
                msg = f"Alerta: señal baja ({signal} dBm) en {ssid}"
                self.alert_label.setText(msg)
                self.alerta_activada.emit(msg)
        else:
            self._below_since = None
            self.alert_label.setText("")

        self.dibujar()

    def dibujar(self) -> None:
        self.indicador_senal.establecer_tema(self.prefs.theme)
        self.grafico.actualizar(
            self.session.intensity.timestamps,
            self.session.intensity.values_dbm,
            self.monitor_combo.currentText(),
            self.prefs.thresholds,
            theme=self.prefs.theme,
        )
