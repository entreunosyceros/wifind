"""Manual de usuario integrado en WiFind."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from wifind import __app_name__, __version__

MANUAL_HTML = f"""
<h1>{__app_name__} — Manual de usuario</h1>
<p>Versión {__version__}. Aplicación de escritorio para analizar redes WiFi,
monitorizar la señal en tiempo real y generar mapas de calor de cobertura sobre planos de planta.</p>

<h2>Inicio rápido</h2>
<ol>
  <li>Ejecuta la aplicación con <code>python3 run_app.py</code>.</li>
  <li>En <b>Escáner WiFi</b> revisa las redes detectadas y selecciona la que te interese.</li>
  <li>En <b>Mapa de calor</b> carga un plano (<b>Archivo → Cargar plano de planta</b>),
      elige la red objetivo y haz clic en el mapa para registrar mediciones.</li>
  <li>Guarda tu trabajo con <b>Archivo → Guardar sesión</b> (<kbd>Ctrl+S</kbd>).</li>
</ol>

<h2>Pestañas principales</h2>

<h3>Escáner WiFi</h3>
<ul>
  <li>Lista las redes cercanas con información RF ampliada (ver tabla inferior).</li>
  <li><b>Clic derecho</b> sobre una red: conectar, monitorizar, usar en mapa de calor, copiar SSID/BSSID.</li>
  <li>Botón <b>Conectar</b>; doble clic inicia monitorización de la red seleccionada.</li>
  <li>Panel <b>Red conectada</b>: botón <b>Desconectar</b> para cerrar la sesión WiFi activa (también en el menú contextual de la red en uso).</li>
  <li>Al conectar, puedes marcar <b>Recordar contraseña</b> para no volver a escribirla en redes WPA/WEP.</li>
  <li>Redes empresariales 802.1X: diálogo específico con PEAP, TTLS o TLS.</li>
  <li>Filtros por SSID, banda, seguridad y señal mínima en la barra superior.</li>
  <li>La fila resaltada en <span style="color:#2e7d32">verde</span> corresponde a la red en uso.</li>
  <li><kbd>F5</kbd> fuerza un nuevo escaneo; el auto-escaneo se activa en la barra de herramientas.</li>
</ul>

<h4>Columnas de la tabla de redes</h4>
<table border="1" cellpadding="4" cellspacing="0">
  <tr><th>Columna</th><th>Significado</th></tr>
  <tr><td><b>En uso</b></td><td>Marca (●) la red a la que estás conectado.</td></tr>
  <tr><td><b>SSID / BSSID</b></td><td>Nombre visible y MAC del punto de acceso.</td></tr>
  <tr><td><b>Señal (dBm / %)</b></td><td>Intensidad recibida y porcentaje equivalente.</td></tr>
  <tr><td><b>Calidad</b></td><td>Indicador de rayas (▁ a ▇): cuantas más, mejor señal.</td></tr>
  <tr><td><b>Canal / Banda</b></td><td>Canal WiFi y banda (2,4 GHz o 5 GHz).</td></tr>
  <tr><td><b>Oculta</b></td><td>Sí si la red no anuncia SSID en las balizas.</td></tr>
  <tr><td><b>Cifrado</b></td><td>Resumen del cifrado (p. ej. WPA2 + PSK + AES-CCMP).</td></tr>
  <tr><td><b>Radio</b></td><td>Estándar 802.11 estimado (n, ac, ax…).</td></tr>
  <tr><td><b>Rate</b></td><td>Velocidad anunciada por el AP (p. ej. 130 Mbit/s).</td></tr>
  <tr><td><b>Ancho (MHz)</b></td><td>Ancho de canal (20, 40, 80 MHz…).</td></tr>
</table>

<h4>Panel «Red conectada»</h4>
<p>Cuando hay enlace WiFi activo, el panel inferior muestra además:</p>
<ul>
  <li><b>Enlace TX / RX</b> — velocidad real de transmisión y recepción (Mbps).</li>
  <li><b>IP, Gateway, DNS</b> — configuración IPv4 de la conexión.</li>
  <li>Cifrado, tipo radio, canal, rate anunciada y ancho de canal de la sesión actual.</li>
</ul>
<p>En Linux estos datos provienen de <code>nmcli</code> e <code>iw</code>; en Windows de <code>netsh</code> e <code>ipconfig</code>;
  en macOS de <code>airport -I</code>. No todos los campos están disponibles en todas las plataformas o adaptadores.</p>

<p>La tabla inferior <b>Puntos de acceso por SSID</b> agrupa varios AP con el mismo nombre de red.</p>

<h3>Intensidad en vivo</h3>
<ul>
  <li>Elige una red y pulsa <b>Iniciar monitoreo</b> para ver la señal en el tiempo.</li>
  <li>El indicador de <b>rayas</b> junto al gráfico muestra la intensidad actual (4 rayas = excelente).</li>
  <li>Las líneas naranja y verde marcan los umbrales débil y bueno (configurables en Preferencias).</li>
  <li>Se puede configurar una alerta si la señal permanece baja durante un intervalo.</li>
</ul>

<h3>Mapa de calor</h3>
<ul>
  <li><b>Clic izquierdo</b> en el mapa: registra una medición en ese punto con la señal de la red objetivo.</li>
  <li><b>Clic derecho</b> sobre un punto medido: eliminar o editar nota.</li>
  <li>Arrastra un punto para moverlo. <b>Deshacer</b> / <b>Rehacer</b> y <kbd>Ctrl+Z</kbd> deshacen mediciones.</li>
  <li><b>Calibrar plano</b>: dibuja una línea sobre una distancia conocida para ajustar la escala.</li>
  <li><b>Shift + clic</b>: coloca waypoints de recorrido (survey).</li>
  <li>Varias plantas: botón <b>+ Piso</b>; cada planta tiene plano, mediciones y paredes propias.</li>
  <li>La barra lateral de colores (<i>Intensidad relativa</i>) aparece cuando hay mediciones:
      verde = buena cobertura, rojo = débil.</li>
</ul>

<h3>Modelo de paredes</h3>
<p>La interpolación sin paredes asume espacio vacío. Para simular obstáculos:</p>
<ol>
  <li>Activa <b>Dibujar paredes</b>.</li>
  <li>Elige material (Pladur ~4 dB, Ladrillo ~8 dB, Hormigón ~15 dB) o atenuación personalizada.</li>
  <li>Arrastra sobre el plano para trazar una pared (vista previa discontinua).</li>
  <li><b>Clic derecho</b> sobre una pared: editar o eliminar.</li>
</ol>
<p>El algoritmo resta la atenuación cuando el rayo medición→píxel cruza una pared.</p>

<h3>Canales</h3>
<ul>
  <li>Histogramas de saturación en 2,4 GHz y 5 GHz.</li>
  <li>Canal recomendado resaltado en verde (menor número de APs en ese canal).</li>
  <li>Tabla inferior con el detalle por canal.</li>
</ul>

<h3>Dispositivos</h3>
<ul>
  <li>Disponible cuando hay conexión WiFi activa con IP asignada.</li>
  <li><b>Escanear dispositivos</b> explora la LAN (tabla ARP/neighbor y ping a la subred).</li>
  <li>El <b>diagrama</b> colorea cada tarjeta según su tipo: router, este equipo, ordenador, teléfono, tablet, IoT u otro.</li>
  <li>La clasificación se infiere del <b>nombre de host</b> (DNS + mDNS) y del prefijo MAC (OUI).</li>
  <li>Los móviles <b>Android</b> suelen anunciarse como <code>Android_…</code> en mDNS; en Linux instala <code>avahi-utils</code>.</li>
  <li>Cada tarjeta muestra el rol, nombre de host (si se resuelve), IP y dirección MAC.</li>
  <li>La leyenda inferior derecha usa los mismos colores que las tarjetas del diagrama.</li>
  <li>Arrastra el <b>fondo</b> del diagrama para desplazar la vista; arrastra un <b>nodo</b> para reorganizarlo.</li>
  <li>La tabla inferior detalla tipo, IP, MAC, nombre y estado.</li>
  <li>Desde el escáner, el botón <b>Ver dispositivos en la red…</b> abre esta pestaña e inicia el escaneo.</li>
  <li><b>Exportar diagrama (PNG)</b> guarda la imagen de topología.</li>
</ul>
<p>Nota: en redes con aislamiento de clientes (AP isolation) puede que solo veas el router y tu propio equipo.</p>

<h3>Histórico</h3>
<ul>
  <li>Evolución del número de redes visibles y señal media durante la sesión.</li>
  <li>Comparar último snapshot con el estado actual del escaneo.</li>
</ul>

<h2>Menú Archivo</h2>
<ul>
  <li><b>Nueva sesión</b> / <b>Abrir</b> / <b>Guardar</b>: proyectos en formato <code>.wifind</code> (JSON + carpeta de assets con planos).</li>
  <li><b>Exportar</b>: mapa de calor e intensidad (PNG/PDF), redes y mediciones (CSV).</li>
  <li><b>Redes escaneadas (CSV)</b> incluye SSID, BSSID, señal, canal, banda, cifrado detallado, tipo radio,
      velocidad anunciada, ancho de canal, red en uso, TX/RX, IP, gateway, DNS y marca temporal.</li>
  <li><b>Generar informe</b>: resumen HTML con mapas embebidos y tabla de redes (en uso, cifrado, radio, rate).</li>
</ul>
<p>El icono en la <b>bandeja del sistema</b> ofrece el mismo menú Archivo con clic derecho;
  clic izquierdo restaura la ventana.</p>

<h2>Menú Ver</h2>
<ul>
  <li>Cambio rápido entre plantas activas.</li>
  <li>Tema claro u oscuro.</li>
</ul>

<h2>Preferencias</h2>
<ul>
  <li>Intervalo de escaneo, umbrales de señal (bueno / aceptable / débil).</li>
  <li>Unidades (metros o pies), carpeta de exportación, tema.</li>
  <li>Parámetros de survey automático (intervalo, paso).</li>
</ul>

<h2>Atajos de teclado</h2>
<table border="0" cellspacing="6">
  <tr><td><kbd>F5</kbd></td><td>Escanear redes</td></tr>
  <tr><td><kbd>Ctrl+S</kbd></td><td>Guardar sesión</td></tr>
  <tr><td><kbd>Ctrl+O</kbd></td><td>Abrir sesión</td></tr>
  <tr><td><kbd>Ctrl+Z</kbd></td><td>Deshacer última medición (mapa de calor)</td></tr>
  <tr><td><kbd>Ctrl+Q</kbd></td><td>Salir</td></tr>
</table>

<h2>Requisitos y solución de problemas</h2>
<ul>
  <li><b>Linux</b>: NetworkManager (<code>nmcli</code>) o <code>iw</code>. Antenas USB suelen aparecer como <code>wlx…</code>.</li>
  <li><b>Windows</b>: adaptador WiFi activo y servicio WLAN.</li>
  <li><b>macOS</b>: puede requerir permisos de red local.</li>
  <li>Si no se detectan redes: comprueba que la interfaz WiFi esté activa
      (<code>nmcli device status</code>) y no bloqueada (<code>rfkill unblock wifi</code>).</li>
</ul>

<p><i>Documentación ampliada y código fuente:
<a href="https://github.com/entreunosyceros/wifind">github.com/entreunosyceros/wifind</a></i></p>
"""


class DialogoManual(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Manual — {__app_name__}")
        self.setMinimumSize(680, 540)
        self.setModal(True)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(MANUAL_HTML)
        browser.setStyleSheet("QTextBrowser { padding: 8px; }")
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
