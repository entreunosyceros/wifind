"""Diálogo de preferencias."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wifind.modelos.preferencias import PreferenciasApp


class DialogoPreferencias(QDialog):
    def __init__(self, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self.setMinimumWidth(420)
        self._prefs = prefs

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        general = QWidget()
        gf = QFormLayout(general)
        self.export_dir = QLineEdit(prefs.export_dir)
        gf.addRow("Carpeta exportación:", self.export_dir)
        self.units = QComboBox()
        self.units.addItems(["m", "ft"])
        self.units.setCurrentText(prefs.units)
        gf.addRow("Unidades:", self.units)
        tabs.addTab(general, "General")

        thresholds = QWidget()
        tf = QFormLayout(thresholds)
        self.excellent = QSpinBox()
        self.excellent.setRange(-100, 0)
        self.excellent.setValue(prefs.threshold_excellent)
        tf.addRow("Excelente (dBm):", self.excellent)
        self.good = QSpinBox()
        self.good.setRange(-100, 0)
        self.good.setValue(prefs.threshold_good)
        tf.addRow("Buena (dBm):", self.good)
        self.fair = QSpinBox()
        self.fair.setRange(-100, 0)
        self.fair.setValue(prefs.threshold_fair)
        tf.addRow("Regular (dBm):", self.fair)
        self.weak = QSpinBox()
        self.weak.setRange(-100, 0)
        self.weak.setValue(prefs.threshold_weak)
        tf.addRow("Débil (dBm):", self.weak)
        self.alert = QSpinBox()
        self.alert.setRange(-100, 0)
        self.alert.setValue(prefs.alert_threshold_dbm)
        tf.addRow("Alerta (dBm):", self.alert)
        tabs.addTab(thresholds, "Umbrales")

        scan = QWidget()
        sf = QFormLayout(scan)
        self.scan_interval = QSpinBox()
        self.scan_interval.setRange(1000, 60000)
        self.scan_interval.setSingleStep(1000)
        self.scan_interval.setValue(prefs.scan_interval_ms)
        sf.addRow("Auto-escaneo (ms):", self.scan_interval)
        self.survey_interval = QSpinBox()
        self.survey_interval.setRange(1, 60)
        self.survey_interval.setValue(prefs.survey_interval_sec)
        sf.addRow("Intervalo recorrido (s):", self.survey_interval)
        self.walk_step = QDoubleSpinBox()
        self.walk_step.setRange(0.1, 10)
        self.walk_step.setValue(prefs.walk_step_m)
        sf.addRow("Paso recorrido (m):", self.walk_step)
        tabs.addTab(scan, "Escaneo")

        appearance = QWidget()
        af = QFormLayout(appearance)
        self.theme = QComboBox()
        self.theme.addItems(["light", "dark"])
        self.theme.setCurrentText(prefs.theme)
        af.addRow("Tema:", self.theme)
        tabs.addTab(appearance, "Apariencia")

        layout.addWidget(tabs)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def aplicar_a(self, prefs: PreferenciasApp) -> None:
        prefs.export_dir = self.export_dir.text().strip()
        prefs.units = self.units.currentText()
        prefs.threshold_excellent = self.excellent.value()
        prefs.threshold_good = self.good.value()
        prefs.threshold_fair = self.fair.value()
        prefs.threshold_weak = self.weak.value()
        prefs.alert_threshold_dbm = self.alert.value()
        prefs.scan_interval_ms = self.scan_interval.value()
        prefs.survey_interval_sec = self.survey_interval.value()
        prefs.walk_step_m = self.walk_step.value()
        prefs.theme = self.theme.currentText()
        prefs.save()
