"""Campo de contraseña con botón mostrar/ocultar."""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class CampoContrasena(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edit)

        self.toggle_btn = QPushButton("Mostrar")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setFixedWidth(72)
        self.toggle_btn.toggled.connect(self._alternar_visibilidad)
        layout.addWidget(self.toggle_btn)

    def _alternar_visibilidad(self, visible: bool) -> None:
        self.edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.toggle_btn.setText("Ocultar" if visible else "Mostrar")

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str) -> None:
        self.edit.setText(text)

    def setFocus(self) -> None:
        self.edit.setFocus()

    def setEnabled(self, enabled: bool) -> None:
        self.edit.setEnabled(enabled)
        self.toggle_btn.setEnabled(enabled)
