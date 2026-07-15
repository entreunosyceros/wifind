"""Pestaña análisis de canales."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from wifind.modelos.preferencias import PreferenciasApp
from wifind.servicios.analisis_canales import analizar_canales
from wifind.ui.grafico_canales import GraficoCanales
from wifind.wifi.red import RedWifi


class PestanaCanales(QWidget):
    def __init__(self, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.prefs = prefs
        layout = QVBoxLayout(self)
        self.rec_label = QLabel("")
        self.rec_label.setWordWrap(True)
        layout.addWidget(self.rec_label)
        self.grafico = GraficoCanales()
        layout.addWidget(self.grafico)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Canal", "Banda", "Redes"])
        layout.addWidget(self.table)

    def establecer_redes(self, networks: list[RedWifi]) -> None:
        analysis = analizar_canales(networks)
        rec_parts = []
        if analysis.canal_recomendado_24ghz:
            rec_parts.append(f"2.4 GHz: canal {analysis.canal_recomendado_24ghz}")
        if analysis.canal_recomendado_5ghz:
            rec_parts.append(f"5 GHz: canal {analysis.canal_recomendado_5ghz}")
        self.rec_label.setText(
            "Canal recomendado — " + ", ".join(rec_parts) if rec_parts else "Sin datos suficientes"
        )
        self.grafico.actualizar(analysis, theme=self.prefs.theme)
        rows = [(r.channel, r.band, r.ap_count) for r in analysis.tabla_saturacion]
        self.table.setRowCount(len(rows))
        for i, (ch, band, count) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(ch)))
            self.table.setItem(i, 1, QTableWidgetItem(band))
            self.table.setItem(i, 2, QTableWidgetItem(str(count)))
