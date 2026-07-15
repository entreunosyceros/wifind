"""Diálogo para conectar a una red WiFi."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from wifind.escaner_wifi import RedWifi, requiere_contrasena
from wifind.servicios.credenciales_wifi import obtener_contrasena, tiene_contrasena_guardada
from wifind.ui.campo_contrasena import CampoContrasena


class DialogoConexion(QDialog):
    def __init__(self, network: RedWifi, parent=None) -> None:
        super().__init__(parent)
        self._network = network
        self.setWindowTitle("Conectar a red WiFi")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        info = QLabel(
            f"<b>{network.ssid}</b><br>"
            f"Acceso: <b>{network.tipo_acceso()}</b> — "
            f"Cifrado: {network.cifrado_detallado or network.security}<br>"
            f"Señal: {network.signal_dbm} dBm ({network.signal_percent} %)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.password_edit = CampoContrasena()
        needs_password = requiere_contrasena(network)
        self.password_edit.setEnabled(needs_password)
        self.remember_cb = QCheckBox("Recordar contraseña para esta red")
        self.remember_cb.setEnabled(needs_password)

        if needs_password:
            form.addRow("Contraseña:", self.password_edit)
            guardada = obtener_contrasena(network.ssid)
            if guardada:
                self.password_edit.setText(guardada)
                self.remember_cb.setChecked(True)
            elif tiene_contrasena_guardada(network.ssid):
                self.remember_cb.setChecked(True)
            layout.addLayout(form)
            layout.addWidget(self.remember_cb)
        else:
            form.addRow("Contraseña:", QLabel("No requerida (red abierta)"))
            layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Conectar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if needs_password:
            self.password_edit.setFocus()
        else:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setFocus()

    def obtener_contrasena_o_nada(self) -> str | None:
        if requiere_contrasena(self._network):
            value = self.password_edit.text()
            return value or None
        return None

    def debe_guardar_contrasena(self) -> bool:
        return self.remember_cb.isChecked() and requiere_contrasena(self._network)

    def debe_olvidar_contrasena(self) -> bool:
        return (
            requiere_contrasena(self._network)
            and not self.remember_cb.isChecked()
            and tiene_contrasena_guardada(self._network.ssid)
        )
