"""Diálogo Acerca de WiFind."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from wifind import __app_name__, __version__

GITHUB_URL = "https://github.com/entreunosyceros/wifind"
LOGO_PATH = Path(__file__).resolve().parents[1] / "img" / "logo.png"

DESCRIPTION = (
    f"{__app_name__} analiza las redes WiFi disponibles en tu dispositivo, "
    "muestra la intensidad de señal en tiempo real y genera mapas de calor "
    "sobre un plano de planta para visualizar la cobertura inalámbrica en "
    "cada zona del espacio."
)


class DialogoAcerca(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {__app_name__}")
        self.setMinimumWidth(420)
        self.setMinimumHeight(520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        if LOGO_PATH.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(LOGO_PATH))
            if pixmap.width() > 320:
                pixmap = pixmap.scaledToWidth(320, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)

        title = QLabel(f"<b>{__app_name__}</b> v{__version__}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(DESCRIPTION)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        github_btn = QPushButton("Ver en GitHub")
        github_btn.clicked.connect(self.abrir_github)
        layout.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def abrir_github(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_URL))
