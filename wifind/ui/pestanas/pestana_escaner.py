"""Pestaña escáner WiFi."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wifind.modelos.preferencias import PreferenciasApp
from wifind.servicios.agrupacion_ap import agrupar_por_ssid
from wifind.servicios.credenciales_wifi import eliminar_contrasena, guardar_contrasena
from wifind.ui.dialogo_conexion import DialogoConexion
from wifind.ui.indicador_senal import IndicadorSenal
from wifind.ui.dialogo_conexion_empresarial import DialogoConexionEmpresarial
from wifind.wifi.red import RedWifi
from wifind.wifi.plataforma import (
    conectar_empresarial,
    desconectar_wifi,
    pista_error_conexion,
    conectar_a_red,
    obtener_red_conectada,
    es_red_empresarial,
)

_COLORES_ACCESO = {
    "Abierta": ("#1B5E20", "#E8F5E9"),
    "Con contraseña": ("#0D47A1", "#E3F2FD"),
    "Empresarial": ("#4A148C", "#F3E5F5"),
}


def _item_acceso(tipo: str) -> QTableWidgetItem:
    etiquetas = {
        "Abierta": "○ Abierta",
        "Con contraseña": "● Con clave",
        "Empresarial": "◆ 802.1X",
    }
    item = QTableWidgetItem(etiquetas.get(tipo, tipo))
    fg, bg = _COLORES_ACCESO.get(tipo, ("#424242", "#FAFAFA"))
    item.setForeground(QColor(fg))
    item.setBackground(QColor(bg))
    font = QFont()
    font.setBold(True)
    item.setFont(font)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item


class PestanaEscaner(QWidget):
    conexion_solicitada = pyqtSignal()
    monitorizacion_solicitada = pyqtSignal(str)
    mapa_calor_solicitado = pyqtSignal(str)
    dispositivos_solicitados = pyqtSignal()

    def __init__(self, prefs: PreferenciasApp, parent=None) -> None:
        super().__init__(parent)
        self.prefs = prefs
        self._networks: list[RedWifi] = []
        self._filtered: list[RedWifi] = []
        self.conectared_ssid: str | None = None
        self._sort_col = -1
        self._sort_asc = True

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Redes WiFi detectadas. Clic derecho para más opciones.<br>"
            "<span style='color:#1B5E20;font-weight:bold'>○ Abierta</span> sin contraseña · "
            "<span style='color:#0D47A1;font-weight:bold'>● Con clave</span> WPA/WEP · "
            "<span style='color:#4A148C;font-weight:bold'>◆ 802.1X</span> empresarial · "
            "<span style='background:#C8E6C9'>verde</span> = red en uso"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        filters = QHBoxLayout()
        self.filter_ssid = QLineEdit()
        self.filter_ssid.setPlaceholderText("Filtrar SSID…")
        self.filter_ssid.textChanged.connect(self.aplicar_filtros)
        filters.addWidget(self.filter_ssid)

        self.filter_band = QComboBox()
        self.filter_band.addItems(["Todas las bandas", "2.4 GHz", "5 GHz"])
        self.filter_band.currentIndexChanged.connect(self.aplicar_filtros)
        filters.addWidget(self.filter_band)

        self.filter_security = QComboBox()
        self.filter_security.addItems(
            ["Toda seguridad", "Abierta", "Con clave", "WPA", "Enterprise"]
        )
        self.filter_security.currentIndexChanged.connect(self.aplicar_filtros)
        filters.addWidget(self.filter_security)

        self.signal_slider = QSlider(Qt.Orientation.Horizontal)
        self.signal_slider.setRange(-100, -30)
        self.signal_slider.setValue(-100)
        self.signal_slider.valueChanged.connect(self.aplicar_filtros)
        filters.addWidget(QLabel("Señal mín:"))
        filters.addWidget(self.signal_slider)
        self.signal_label = QLabel("-100 dBm")
        self.signal_slider.valueChanged.connect(
            lambda v: self.signal_label.setText(f"{v} dBm")
        )
        filters.addWidget(self.signal_label)
        layout.addLayout(filters)

        self.network_table = QTableWidget(0, 14)
        self.network_table.setHorizontalHeaderLabels(
            [
                "En uso",
                "Acceso",
                "SSID",
                "BSSID",
                "Señal (dBm)",
                "Señal (%)",
                "Calidad",
                "Canal",
                "Banda",
                "Oculta",
                "Cifrado",
                "Radio",
                "Rate",
                "Ancho (MHz)",
            ]
        )
        self.network_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.network_table.setColumnWidth(1, 100)
        self.network_table.setColumnWidth(6, 64)
        self.network_table.horizontalHeader().sectionClicked.connect(self.ordenar_por_columna)
        self.network_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.network_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.network_table.setAlternatingRowColors(True)
        self.network_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.network_table.customContextMenuRequested.connect(self.menu_contextual)
        self.network_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.network_table.itemDoubleClicked.connect(self.al_doble_clic)
        layout.addWidget(self.network_table)

        bar = QHBoxLayout()
        self.selected_label = QLabel("Red seleccionada: ninguna")
        bar.addWidget(self.selected_label, stretch=1)
        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self.conectar)
        bar.addWidget(self.connect_btn)
        layout.addLayout(bar)

        ap_group = QGroupBox("Puntos de acceso por SSID")
        ap_layout = QVBoxLayout(ap_group)
        self.ap_table = QTableWidget(0, 4)
        self.ap_table.setHorizontalHeaderLabels(["SSID", "BSSID", "Señal", "Canal"])
        self.ap_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ap_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        ap_layout.addWidget(self.ap_table)
        layout.addWidget(ap_group)

        connected_box = QGroupBox("Red conectada")
        cl = QVBoxLayout(connected_box)
        signal_connected = QHBoxLayout()
        signal_connected.addWidget(QLabel("Intensidad:"))
        self.connected_indicator = IndicadorSenal(theme=self.prefs.theme)
        signal_connected.addWidget(self.connected_indicator)
        signal_connected.addStretch()
        cl.addLayout(signal_connected)
        self.connected_label = QLabel("—")
        self.connected_label.setWordWrap(True)
        cl.addWidget(self.connected_label)
        connected_actions = QHBoxLayout()
        self.disconnect_btn = QPushButton("Desconectar")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.desconectar)
        connected_actions.addWidget(self.disconnect_btn)
        self.devices_btn = QPushButton("Ver dispositivos en la red…")
        self.devices_btn.setEnabled(False)
        self.devices_btn.clicked.connect(self.dispositivos_solicitados.emit)
        connected_actions.addWidget(self.devices_btn)
        connected_actions.addStretch()
        cl.addLayout(connected_actions)
        layout.addWidget(connected_box)

    def establecer_redes(self, networks: list[RedWifi]) -> None:
        self._networks = networks
        self.aplicar_filtros()
        self.actualizar_tabla_ap()
        self.actualizar_conectada()

    def red_seleccionada(self) -> RedWifi | None:
        rows = self.network_table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._filtered):
            return self._filtered[row]
        return None

    def aplicar_filtros(self) -> None:
        text = self.filter_ssid.text().strip().lower()
        min_signal = self.signal_slider.value()
        band = self.filter_band.currentText()
        sec = self.filter_security.currentText()

        filtered = []
        for net in self._networks:
            if text and text not in net.ssid.lower():
                continue
            if net.signal_dbm < min_signal:
                continue
            if band != "Todas las bandas" and net.band != band:
                continue
            sec_l = net.security.lower()
            acceso = net.tipo_acceso()
            if sec == "Abierta" and acceso != "Abierta":
                continue
            if sec == "Con clave" and acceso != "Con contraseña":
                continue
            if sec == "WPA" and "wpa" not in sec_l and acceso != "Con contraseña":
                continue
            if sec == "Enterprise" and acceso != "Empresarial":
                continue
            filtered.append(net)

        self._filtered = filtered
        self.rellenar_tabla()

    def rellenar_tabla(self) -> None:
        connected = obtener_red_conectada()
        self.conectared_ssid = connected.ssid if connected else None

        data = list(self._filtered)
        if self._sort_col >= 0:
            if self._sort_col == 1:
                data.sort(key=lambda n: n.tipo_acceso(), reverse=not self._sort_asc)
            else:
                keys = [
                    "en_uso",
                    None,
                    "ssid",
                    "bssid",
                    "signal_dbm",
                    "signal_percent",
                    "signal_dbm",
                    "channel",
                    "band",
                    "oculta",
                    "cifrado_detallado",
                    "tipo_radio",
                    "velocidad_anunciada",
                    "ancho_canal_mhz",
                ]
                key = keys[self._sort_col]
                if key:
                    data.sort(key=lambda n: getattr(n, key) or "", reverse=not self._sort_asc)

        self.network_table.setRowCount(len(data))
        for row, net in enumerate(data):
            en_uso = net.en_uso or (
                connected is not None
                and net.ssid == connected.ssid
                and (not net.bssid or not connected.bssid or net.bssid == connected.bssid)
            )
            acceso = net.tipo_acceso()
            items = [
                "●" if en_uso else "",
                acceso,
                net.ssid,
                net.bssid,
                str(net.signal_dbm),
                f"{net.signal_percent} %",
                "",
                str(net.channel) if net.channel else "—",
                net.band or "—",
                "Sí" if net.oculta else "No",
                net.cifrado_detallado or net.security,
                net.tipo_radio or "—",
                net.velocidad_anunciada or "—",
                str(net.ancho_canal_mhz) if net.ancho_canal_mhz else "—",
            ]
            for col, text in enumerate(items):
                if col == 1:
                    item = _item_acceso(acceso)
                elif col == 6:
                    continue
                else:
                    item = QTableWidgetItem(text)
                if en_uso:
                    if col != 1:
                        item.setBackground(QColor("#C8E6C9"))
                    else:
                        fg, _ = _COLORES_ACCESO.get(acceso, ("#424242", "#FAFAFA"))
                        item.setBackground(QColor("#C8E6C9"))
                        item.setForeground(QColor(fg))
                self.network_table.setItem(row, col, item)

            indicador = IndicadorSenal(theme=self.prefs.theme)
            indicador.establecer_barras(
                net.nivel_barras_senal(self.prefs.thresholds),
                signal_dbm=net.signal_dbm,
            )
            celda = QWidget()
            celda_layout = QHBoxLayout(celda)
            celda_layout.setContentsMargins(6, 2, 6, 2)
            celda_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            celda_layout.addWidget(indicador)
            if en_uso:
                celda.setStyleSheet("background-color: #C8E6C9;")
            self.network_table.setCellWidget(row, 6, celda)

    def ordenar_por_columna(self, col: int) -> None:
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.rellenar_tabla()

    def actualizar_tabla_ap(self) -> None:
        groups = agrupar_por_ssid(self._networks)
        rows = sum(len(v) for v in groups.values())
        self.ap_table.setRowCount(rows)
        r = 0
        for ssid, nets in sorted(groups.items()):
            for net in sorted(nets, key=lambda n: n.signal_dbm, reverse=True):
                self.ap_table.setItem(r, 0, QTableWidgetItem(ssid))
                self.ap_table.setItem(r, 1, QTableWidgetItem(net.bssid))
                self.ap_table.setItem(r, 2, QTableWidgetItem(f"{net.signal_dbm} dBm"))
                self.ap_table.setItem(r, 3, QTableWidgetItem(str(net.channel or "—")))
                r += 1

    def actualizar_conectada(self) -> None:
        connected = obtener_red_conectada()
        if connected:
            tx = (
                f"{connected.tx_bitrate_mbps:.0f} Mbps"
                if connected.tx_bitrate_mbps is not None
                else "—"
            )
            rx = (
                f"{connected.rx_bitrate_mbps:.0f} Mbps"
                if connected.rx_bitrate_mbps is not None
                else "—"
            )
            ancho = (
                f"{connected.ancho_canal_mhz} MHz"
                if connected.ancho_canal_mhz is not None
                else "—"
            )
            self.connected_indicator.establecer_barras(
                connected.nivel_barras_senal(self.prefs.thresholds),
                signal_dbm=connected.signal_dbm,
            )
            self.connected_label.setText(
                f"<b>{connected.ssid}</b> ({connected.bssid or '—'})<br>"
                f"Señal: {connected.signal_dbm} dBm ({connected.signal_percent} %)<br>"
                f"Cifrado: {connected.cifrado_detallado or connected.security} — "
                f"Radio: {connected.tipo_radio or '—'} — "
                f"Canal: {connected.channel or '—'} — Banda: {connected.band or '—'}<br>"
                f"Rate anunciada: {connected.velocidad_anunciada or '—'} — "
                f"Ancho canal: {ancho}<br>"
                f"Enlace TX: {tx} — RX: {rx}<br>"
                f"IP: {connected.ip or '—'} — Gateway: {connected.gateway or '—'} — "
                f"DNS: {connected.dns or '—'}"
            )
            self.devices_btn.setEnabled(bool(connected.ip))
            self.disconnect_btn.setEnabled(True)
        else:
            self.connected_indicator.establecer_barras(0)
            self.connected_label.setText("No hay conexión WiFi activa detectada.")
            self.devices_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)

    def _on_selection_changed(self) -> None:
        net = self.red_seleccionada()
        if net:
            acceso = net.tipo_acceso()
            clave_txt = "sin clave" if acceso == "Abierta" else acceso.lower()
            self.selected_label.setText(
                f"Red seleccionada: {net.ssid} ({net.signal_dbm} dBm) — {clave_txt}"
            )
            self.connect_btn.setText(
                "Conectar" if acceso != "Abierta" else "Conectar (abierta)"
            )
            self.connect_btn.setEnabled(True)
            rows = self.network_table.selectionModel().selectedRows()
            if rows:
                for col in range(self.network_table.columnCount()):
                    item = self.network_table.item(rows[0].row(), col)
                    if item and net.ssid != self.conectared_ssid:
                        item.setBackground(QColor("#BBDEFB"))
        else:
            self.selected_label.setText("Red seleccionada: ninguna")
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Conectar")

    def al_doble_clic(self, item: QTableWidgetItem) -> None:
        net = self.red_seleccionada()
        if net:
            self.monitorizacion_solicitada.emit(net.ssid)

    def menu_contextual(self, pos) -> None:
        net = self.red_seleccionada()
        if not net:
            return
        menu = QMenu(self)
        connected = obtener_red_conectada()
        en_uso = connected and net.ssid == connected.ssid and (
            not net.bssid or not connected.bssid or net.bssid == connected.bssid
        )
        if en_uso:
            menu.addAction("Desconectar", self.desconectar)
            menu.addSeparator()
        menu.addAction("Conectar", self.conectar)
        menu.addAction("Monitorizar", lambda: self.monitorizacion_solicitada.emit(net.ssid))
        menu.addAction("Usar en mapa", lambda: self.mapa_calor_solicitado.emit(net.ssid))
        menu.addAction("Copiar SSID", lambda: self.copiar(net.ssid))
        menu.addAction("Copiar BSSID", lambda: self.copiar(net.bssid))
        menu.exec(self.network_table.viewport().mapToGlobal(pos))

    def copiar(self, text: str) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)

    def conectar(self) -> None:
        net = self.red_seleccionada()
        if not net:
            return
        pwd: str | None = None
        dlg: DialogoConexion | DialogoConexionEmpresarial | None = None
        if es_red_empresarial(net):
            dlg = DialogoConexionEmpresarial(net, self)
            if not dlg.exec():
                return
            p = dlg.params()
            ok, msg = conectar_empresarial(net, **p)
        else:
            dlg = DialogoConexion(net, self)
            if not dlg.exec():
                return
            pwd = dlg.obtener_contrasena_o_nada()
            ok, msg = conectar_a_red(net, pwd)

        if ok:
            if isinstance(dlg, DialogoConexion):
                if dlg.debe_guardar_contrasena() and pwd:
                    guardar_contrasena(net.ssid, pwd)
                elif dlg.debe_olvidar_contrasena():
                    eliminar_contrasena(net.ssid)
            QMessageBox.information(self, "Conexión WiFi", msg)
            self.conexion_solicitada.emit()
        else:
            QMessageBox.warning(self, "Error", f"{msg}\n\n{pista_error_conexion()}")

    def desconectar(self) -> None:
        connected = obtener_red_conectada()
        if not connected:
            QMessageBox.information(
                self,
                "Desconectar WiFi",
                "No hay conexión WiFi activa.",
            )
            return
        ok, msg = desconectar_wifi()
        if ok:
            QMessageBox.information(self, "Desconectar WiFi", msg)
            self.conexion_solicitada.emit()
        else:
            QMessageBox.warning(self, "Error", f"{msg}\n\n{pista_error_conexion()}")
