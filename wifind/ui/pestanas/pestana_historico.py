"""Pestaña histórico de escaneos."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wifind.modelos.preferencias import PreferenciasApp
from wifind.modelos.sesion import SesionApp
from wifind.ui.grafico_historico import GraficoHistorico


class PestanaHistorico(QWidget):
    def __init__(self, session: SesionApp, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self.prefs = prefs
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Evolución de escaneos WiFi en esta sesión."))
        self.grafico = GraficoHistorico()
        layout.addWidget(self.grafico)

        btns = QHBoxLayout()
        self.compare_btn = QPushButton("Comparar último vs actual")
        self.compare_btn.clicked.connect(self.comparar)
        btns.addWidget(self.compare_btn)
        btns.addStretch()
        layout.addLayout(btns)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Hora", "Redes", "Señal media"])
        layout.addWidget(self.table)
        self.comparar_label = QLabel("")
        layout.addWidget(self.comparar_label)

        self._current_count = 0
        self._current_avg: float | None = None
        self.refresh()

    def refresh(self, current_count: int = 0, current_avg: float | None = None) -> None:
        snaps = self.session.scan_history
        self.grafico.actualizar(snaps, theme=self.prefs.theme)
        self.table.setRowCount(len(snaps))
        for i, s in enumerate(snaps):
            from datetime import datetime
            t = datetime.fromtimestamp(s.timestamp).strftime("%H:%M:%S")
            avg = f"{s.senal_media_dbm:.0f} dBm" if s.senal_media_dbm else "—"
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(t))
            self.table.setItem(i, 2, QTableWidgetItem(str(s.numero_redes)))
            self.table.setItem(i, 3, QTableWidgetItem(avg))
        self._current_count = current_count
        self._current_avg = current_avg

    def comparar(self) -> None:
        if not self.session.scan_history:
            self.comparar_label.setText("Sin snapshots previos.")
            return
        last = self.session.scan_history[-1]
        diff = self._current_count - last.numero_redes
        avg_diff = ""
        if self._current_avg and last.senal_media_dbm:
            avg_diff = f", Δ señal media: {self._current_avg - last.senal_media_dbm:+.0f} dBm"
        self.comparar_label.setText(
            f"Último snapshot: {last.numero_redes} redes. "
            f"Actual: {self._current_count} (Δ {diff:+d}){avg_diff}"
        )
