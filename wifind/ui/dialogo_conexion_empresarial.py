"""Diálogo de conexión 802.1X empresarial."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from wifind.wifi.red import RedWifi
from wifind.ui.campo_contrasena import CampoContrasena


class DialogoConexionEmpresarial(QDialog):
    def __init__(self, network: RedWifi, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conectar red empresarial (802.1X)")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"<b>{network.ssid}</b><br>Seguridad: {network.security}"
            )
        )

        form = QFormLayout()
        self.eap_method = QComboBox()
        self.eap_method.addItems(["peap", "ttls", "tls"])
        form.addRow("Método EAP:", self.eap_method)

        self.identity = QLineEdit()
        form.addRow("Usuario / identidad:", self.identity)

        self.password = CampoContrasena()
        form.addRow("Contraseña:", self.password)

        self.ca_cert = QLineEdit()
        ca_row = QHBoxLayout()
        ca_row.addWidget(self.ca_cert)
        ca_btn = QPushButton("…")
        ca_btn.clicked.connect(lambda: self._browse(self.ca_cert))
        ca_row.addWidget(ca_btn)
        form.addRow("Certificado CA:", ca_row)

        self.client_cert = QLineEdit()
        cc_row = QHBoxLayout()
        cc_row.addWidget(self.client_cert)
        cc_btn = QPushButton("…")
        cc_btn.clicked.connect(lambda: self._browse(self.client_cert))
        cc_row.addWidget(cc_btn)
        form.addRow("Certificado cliente:", cc_row)

        self.client_cert_password = CampoContrasena()
        form.addRow("Contraseña cert. cliente:", self.client_cert_password)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Conectar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self, field: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar certificado",
            "",
            "Certificados (*.pem *.crt *.cer *.p12 *.pfx);;Todos (*.*)",
        )
        if path:
            field.setText(path)

    def params(self) -> dict:
        return {
            "eap_method": self.eap_method.currentText(),
            "identity": self.identity.text().strip(),
            "password": self.password.text() or None,
            "ca_cert_path": self.ca_cert.text().strip() or None,
            "client_cert_path": self.client_cert.text().strip() or None,
            "client_cert_password": self.client_cert_password.text() or None,
        }
