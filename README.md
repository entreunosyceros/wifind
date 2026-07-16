# WiFind

<img width="1915" height="1046" alt="about-windfind" src="https://github.com/user-attachments/assets/c684781e-c9c5-4af6-b21a-63b585379ebb" />

**WiFind** es una aplicación de escritorio multiplataforma (Windows y Linux) para analizar redes WiFi, monitorizar la intensidad de señal en tiempo real y generar mapas de calor de cobertura sobre planos de planta.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green.svg)
![Licencia](https://img.shields.io/badge/Licencia-MIT-lightgrey.svg)

## Características principales

<img width="1922" height="1045" alt="interfaz-wifind" src="https://github.com/user-attachments/assets/80792b0d-e69b-4d46-91be-898ec19a7e22" />

- **Escáner WiFi** — Detección de redes cercanas con señal (dBm, % e indicador de rayas), canal, banda, tipo de acceso (abierta / con clave / 802.1X), cifrado detallado, tipo radio (802.11n/ac/ax), velocidad anunciada, ancho de canal, red oculta y red en uso; panel de conexión activa con IP, gateway, DNS y velocidad real TX/RX
- **Conexión y desconexión WiFi** — Conectar a redes WPA/WPA2/WPA3 y abiertas desde el escáner; desconectar de la red activa; soporte 802.1X empresarial (PEAP, TTLS, TLS) con certificados; mensajes claros en español (sin salida técnica de `nmcli`/`netsh`)
- **Intensidad en vivo** — Gráfico temporal de la señal recibida con alertas configurables
- **Mapa de calor** — Mediciones sobre plano de planta con interpolación RBF (SciPy)
- **Escala del plano** — Calibra con una distancia conocida («esta línea mide 8 m») para medir distancias, mostrar radios de cobertura, superficie en m² y densidad de puntos
- **Marcadores de AP** — Coloca Router, AP o Repetidor sobre el plano con nombre visible
- **Habitaciones** — Dibuja Salón, Dormitorio, Cocina… y el informe evalúa cada una (Excelente / Buena / Aceptable / Deficiente)
- **Modelo de paredes** — Dibuja obstáculos (pladur, ladrillo, hormigón o atenuación personalizada) que afectan a la interpolación
- **Multi-planta** — Varios pisos con planos, mediciones y paredes independientes
- **Análisis de canales** — Histograma de saturación y recomendación de canal óptimo
- **Dispositivos en la red** — Tras conectarte, escanea la LAN (ARP + ping) y muestra un diagrama con tarjetas coloreadas (router, este equipo, otros) con rol, nombre de host, IP y MAC; leyenda acorde a los colores del diagrama
- **Sesiones `.wifind`** — Guardar y cargar proyectos completos
- **Exportación** — PNG, PDF y CSV; informe HTML con resumen narrativo para el cliente
- **Survey por waypoints** — Recorrido asistido con puntos de ruta
- **Temas** — Interfaz clara u oscura
- **Router de referencia** — Detecta el gateway en la LAN y permite mostrar la cobertura respecto a su posición en el plano

## Requisitos del sistema

| Plataforma | Herramientas WiFi |
|------------|-------------------|
| **Windows** | Adaptador WiFi activo, servicio WLAN |
| **Linux** | NetworkManager (`nmcli`) o `iw` |

### Dependencias Python

- PyQt6 ≥ 6.6
- matplotlib ≥ 3.8
- numpy ≥ 1.26
- scipy ≥ 1.11
- jinja2 ≥ 3.1

## Instalación

```bash
git clone https://github.com/entreunosyceros/wifind.git
cd wifind
python3 run_app.py
```

La primera ejecución crea automáticamente un entorno virtual (`.venv`), instala las dependencias y arranca la aplicación.

### Instalación manual de dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

## Uso rápido

<img width="1915" height="1047" alt="intensidad" src="https://github.com/user-attachments/assets/32727c75-151f-42fd-bdc0-242a19ee761c" />

1. Ejecuta `python3 run_app.py`
2. En **Escáner WiFi** verás las redes detectadas con detalle RF (cifrado, radio, rate, ancho de canal, etc.):
   - Selecciona una red y pulsa **Conectar**, o usa el menú contextual (clic derecho)
   - La red en uso aparece resaltada en **verde**; desde el panel **Red conectada** puedes **Desconectar**
   - Clic derecho sobre la red activa también ofrece **Desconectar**
3. En **Intensidad en vivo** elige una red y pulsa **Iniciar monitoreo**
4. En **Mapa de calor**:
   - Carga un plano: **Archivo → Cargar plano de planta**
   - Selecciona la red objetivo
   - **Calibra el plano** (ver abajo) para trabajar en metros reales
   - Haz clic en el mapa para registrar mediciones
   - Usa **Shift + clic** para colocar waypoints de survey
5. Guarda tu trabajo: **Archivo → Guardar sesión**
6. Con conexión activa, abre **Dispositivos** para explorar la LAN o exporta el diagrama de topología

### Escala del plano

La calibración convierte píxeles del plano en metros (o pies) reales. Es la base para medir distancias, radios y superficies:

1. Pulsa **Calibrar plano**
2. Arrastra una línea sobre una distancia conocida (p. ej. un pasillo de **8 metros**)
3. Indica la longitud real cuando se te pida
4. A partir de ahí puedes:
   - **Medir distancia**: arrastra una línea y verás la longitud en m/ft
   - **Mostrar radio de cobertura**: círculos a N metros alrededor de cada punto medido
   - Ver **superficie** (m² / ft²), cobertura buena/débil en área real y **densidad de puntos**

Sin calibrar, el mapa sigue funcionando en coordenadas de plano; solo faltan las métricas físicas.

### Marcadores de AP en el plano

Puedes anotar dónde está cada equipo WiFi:

1. Pulsa **Colocar AP**
2. Elige el tipo (**Router**, **AP** o **Repetidor**) y un nombre (p. ej. «AP Oficina»)
3. Haz **clic** en el plano para colocarlo
4. **Clic derecho** sobre un marcador: editar o eliminar; arrástralo para moverlo

Los marcadores se guardan en la sesión `.wifind` (`access_points` por planta) y aparecen también en exportaciones e informes.

### Informe para el cliente

**Archivo → Generar informe…** crea un HTML pensado para entregar a alguien que no interpreta mapas de calor:

1. **Resumen** en lenguaje natural (redes detectadas, canal recomendado, % de cobertura, zonas deficientes, recomendaciones)
2. Mapas por planta con habitaciones evaluadas
3. Detalle técnico (tablas) al final

Si el router está marcado en el plano, el resumen puede indicar la distancia a las zonas débiles.

### Router y cobertura relativa

1. En **Dispositivos**, el **gateway se identifica automáticamente como router**
2. Pulsa **Colocar router en el mapa** y haz clic donde está físicamente
3. Activa **Cobertura respecto al router** en el mapa de calor (círculos de distancia)
4. Clic derecho en un AP → **Usar como router de referencia**

### Habitaciones y cobertura por zona

Puedes delimitar estancias sobre el plano y obtener una valoración por habitación:

1. Pulsa **Dibujar habitaciones**
2. Elige un nombre (Salón, Dormitorio, Cocina, Despacho…)
3. **Arrastra** un rectángulo sobre la zona
4. Con mediciones, cada habitación se clasifica como **Excelente**, **Buena**, **Aceptable** o **Deficiente** (según los umbrales de Preferencias)
5. El **informe HTML** incluye un resumen por habitación

### Conexión y desconexión WiFi

| Acción | Dónde | Descripción |
|--------|-------|-------------|
| **Conectar** | Botón o menú contextual | Abre el diálogo de contraseña (WPA) o 802.1X (empresarial). Opción **Recordar contraseña** en redes con clave |
| **Desconectar** | Panel «Red conectada» o menú contextual de la red en uso | Cierra la sesión WiFi activa y refresca el escaneo |

Los mensajes de éxito y error se muestran en **español claro** (p. ej. *Conectado correctamente a la red MiWiFi*), sin rutas D-Bus ni salida cruda del sistema.

**Comandos usados por plataforma**

| Plataforma | Conectar | Desconectar |
|------------|----------|-------------|
| **Linux** | `nmcli device wifi connect` | `nmcli device disconnect` |
| **Windows** | `netsh wlan connect` | `netsh wlan disconnect` |

### Mapa de calor con paredes

<img width="1920" height="1046" alt="mapa-de-calor" src="https://github.com/user-attachments/assets/d4c2ce44-da53-4c47-88f7-918dd110bb51" />

La interpolación pura (RBF/IDW) asume espacio vacío: entre dos mediciones lejanas genera una rampa suave aunque haya una pared real. WiFind permite simular obstáculos:

1. Pulsa **Dibujar paredes** en la pestaña del mapa de calor
2. Elige el **material** (Pladur ~4 dB, Ladrillo ~8 dB, Hormigón ~15 dB) o **Personalizado**
3. Ajusta la **atenuación (dB)** si necesitas un valor distinto al preset
4. **Arrastra** sobre el plano: verás una vista previa discontinua mientras dibujas
5. **Clic derecho** sobre una pared existente para **editarla** o **eliminarla**
6. **Limpiar paredes** borra todas las de la planta activa

Cuando hay paredes, el algoritmo resta su atenuación acumulada en cada rayo *medición → píxel* que las cruza, produciendo transiciones más realistas entre habitaciones y pasillos.

Las paredes se guardan en la sesión `.wifind` (campo `obstaculos` por planta) y se aplican también en exportaciones e informes HTML.

### Datos WiFi en el escáner

La pestaña **Escáner WiFi** muestra, por cada red detectada:

| Campo | Descripción |
|-------|-------------|
| **En uso** | Marca (●) la red a la que estás conectado; la fila se resalta en verde |
| **Acceso** | ○ Abierta · ● Con clave · ◆ 802.1X empresarial |
| **SSID / BSSID** | Nombre de la red y dirección MAC del punto de acceso |
| **Señal** | Intensidad en dBm y porcentaje |
| **Calidad** | Indicador de rayas (▁ a ▇): cuantas más, mejor señal |
| **Canal / Banda** | Canal WiFi y banda (2,4 GHz o 5 GHz) |
| **Oculta** | Red que no emite SSID en las balizas |
| **Cifrado** | Resumen legible (p. ej. WPA2 + PSK + AES-CCMP) |
| **Radio** | Estándar estimado (802.11n, 802.11ac, 802.11ax…) |
| **Rate** | Velocidad anunciada por el AP (p. ej. 130 Mbit/s) |
| **Ancho (MHz)** | Ancho de canal (20, 40, 80 MHz…) |

El panel **Red conectada** (solo con enlace activo) añade:

| Campo / acción | Descripción |
|----------------|-------------|
| **Indicador de rayas** | Intensidad de la señal de la conexión actual |
| **Enlace TX / RX** | Velocidad real de transmisión y recepción en Mbps |
| **IP** | Dirección IPv4 asignada |
| **Gateway** | Puerta de enlace predeterminada |
| **DNS** | Servidores DNS configurados |
| **Desconectar** | Botón para cerrar la sesión WiFi activa |
| **Ver dispositivos…** | Abre la pestaña Dispositivos e inicia el escaneo LAN |

**Fuentes por plataforma**

| Plataforma | Escaneo | Conexión activa |
|------------|---------|-----------------|
| **Linux** | `nmcli` (RATE, IN-USE, WPA/RSN-FLAGS, BANDWIDTH) o `iw scan` | `nmcli` + `iw link` (TX/RX) |
| **Windows** | `netsh wlan show networks` (Radio type, Cipher) | `netsh wlan show interfaces` + `ipconfig` |

Los mismos campos se incluyen al exportar **Redes escaneadas (CSV)** y en la tabla de redes del **informe HTML**.

### Dispositivos en la red local

<img width="1920" height="1045" alt="dispositivos" src="https://github.com/user-attachments/assets/cade8787-18ef-4512-b237-c796f004a482" />

Cuando estás conectado a una red WiFi con IP asignada:

1. Ve a la pestaña **Dispositivos** o pulsa **Ver dispositivos en la red…** en el escáner
2. Pulsa **Escanear dispositivos** — explora la subred (tabla ARP/neighbor + ping paralelo) con barra de progreso
3. El **diagrama** colorea cada tarjeta según su **tipo** detectado:

   | Color | Tipo |
   |-------|------|
   | Naranja | Router / gateway |
   | Verde | Este equipo |
   | Azul | Ordenador |
   | Verde oscuro | Chromecast |
   | Rojo | Cámara IP |
   | Morado | iPhone / teléfono |
   | **Verde Android** | **Móvil o tablet Android** (nombre `Android_…` vía mDNS) |
   | Verde azulado | Tablet |
   | Gris | IoT / Smart TV / impresora |
   | Azul claro | Dispositivo sin clasificar |

   La clasificación usa el **nombre de host** (p. ej. `Android_…`, `iPhone`, `DESKTOP-…`) obtenido por DNS inverso y **mDNS** (`avahi-resolve` en Linux), lookup local de **fabricante por MAC (OUI)** y, opcionalmente, un escaneo ligero de puertos.

   En Linux instala `avahi-utils` si no detecta móviles Android. Muchos Android usan MAC aleatoria y solo se identifican por mDNS.
   Si quieres ampliar fabricantes OUI, crea `~/.config/wifind/oui.csv` con formato `AA:BB:CC,Fabricante`.

4. Cada tarjeta muestra el tipo, nombre de host (si se resuelve), IP y MAC
5. La **leyenda** inferior muestra solo los tipos presentes en el escaneo
6. **Arrastra** el fondo para mover la vista o un nodo para reorganizarlo
7. La **tabla** inferior lista tipo, IP, MAC, nombre y estado
8. **Exportar diagrama (PNG)** guarda la topología con la disposición actual

Al conectar a una red WPA, puedes marcar **Recordar contraseña** en el diálogo de conexión. Se guarda en `~/.config/wifind/wifi_credentials.json` (solo lectura para tu usuario).

Limitaciones: algunas redes usan **aislamiento de clientes** (AP isolation) y ocultan otros equipos; el escaneo puede tardar unos segundos en subredes /24.

### Atajos de teclado

<img width="1919" height="1047" alt="manuall-usuario" src="https://github.com/user-attachments/assets/679d225f-d284-459b-ace4-46fc45381321" />

| Atajo | Acción |
|-------|--------|
| `F5` | Escanear redes |
| `Ctrl+S` | Guardar sesión |
| `Ctrl+O` | Abrir sesión |
| `Ctrl+Z` | Deshacer última medición |
| `Ctrl+Q` | Salir |

## Estructura del proyecto

```
wifind/
├── mapa_calor.py              # Mapas de calor, interpolación RBF y modelo de paredes
├── escaner_wifi.py            # Compatibilidad (redirige a wifi.plataforma)
├── modelos/
│   ├── sesion.py              # Sesión de trabajo (.wifind)
│   ├── medicion.py            # Mediciones, obstáculos (paredes) y puntos de ruta
│   ├── preferencias.py        # Configuración de usuario
│   ├── dispositivo_red.py     # Dispositivos LAN detectados
│   └── instantanea_escaneo.py # Histórico de escaneos
├── servicios/
│   ├── exportacion.py         # Exportar PNG/PDF/CSV
│   ├── informe.py             # Informe HTML
│   ├── analisis_canales.py    # Análisis RF por canal
│   ├── cobertura.py           # Estadísticas de cobertura
│   ├── escala_plano.py        # Escala px↔m, distancias, área y densidad
│   ├── habitaciones.py        # Evaluación de cobertura por habitación
│   ├── narrativa_informe.py   # Resumen ejecutivo en lenguaje natural
│   ├── agrupacion_ap.py       # Agrupación de AP por SSID
│   ├── descubrimiento_lan.py  # Escaneo ARP/ping de la LAN
│   ├── credenciales_wifi.py   # Contraseñas WiFi recordadas
│   └── recorrido.py           # Motor de survey automático
├── wifi/
│   ├── red.py                 # Modelo RedWifi
│   ├── plataforma.py          # Fachada multiplataforma
│   ├── mensajes.py            # Mensajes legibles de conexión/desconexión
│   ├── linux.py               # Backend Linux (nmcli/iw)
│   └── windows.py             # Backend Windows (netsh)
└── ui/
    ├── ventana_principal.py   # Ventana principal
    ├── indicador_senal.py     # Widget de rayas de señal
    ├── grafico_dispositivos.py # Diagrama de topología LAN
    ├── dialogo_acerca.py
    ├── dialogo_conexion.py
    ├── dialogo_conexion_empresarial.py
    ├── dialogo_preferencias.py
    ├── dialogo_manual.py
    └── pestanas/
        ├── pestana_escaner.py
        ├── pestana_intensidad.py
        ├── pestana_mapa_calor.py
        ├── pestana_canales.py
        ├── pestana_dispositivos.py
        └── pestana_historico.py
run_app.py                     # Punto de entrada
requirements.txt
```

## Formato de sesión `.wifind`

Las sesiones se guardan en JSON con extensión `.wifind`. Al guardar, los planos de planta se copian a una carpeta `{nombre}_assets/` junto al archivo de sesión.

Cada planta (`floors[]`) incluye:

- `measurements` — puntos medidos con coordenadas y señal en dBm
- `obstaculos` — segmentos de pared con `material` y `atenuacion_db`
- `waypoints`, `calibration`, `access_points`, `habitaciones`, `floor_plan_path`, etc.

## Configuración

Las preferencias se almacenan en:

- Linux: `~/.config/wifind/settings.json`
- Windows: `%USERPROFILE%\.config\wifind\settings.json` (o equivalente)

Opciones configurables: intervalo de escaneo, umbrales de señal, unidades (m/ft), tema, carpeta de exportación, parámetros de survey, escaneo ligero de puertos LAN (opcional) y timeout de puertos.

Consulta el **Manual de usuario** integrado en **Opciones → Manual…** (incluye descripción de columnas del escáner, paredes, exportación y atajos).

## Solución de problemas

### Linux: no se detectan redes

```bash
# Comprueba que la antena/interfaz WiFi existe
nmcli device status
ip link show

# Escaneo manual (sustituye wlx... por tu interfaz USB)
nmcli device wifi rescan ifname wlx000e8e0ce1d1
nmcli device wifi list
```

Si `nmcli` muestra redes pero WiFind no, actualiza a la última versión: versiones anteriores fallaban al interpretar direcciones MAC (BSSID) con `:` escapados en la salida de NetworkManager.

Antenas USB suelen aparecer como `wlx…` o `wlan…`. Si la interfaz está bloqueada:

```bash
rfkill list
rfkill unblock wifi
```

Alternativa sin NetworkManager:

```bash
sudo iw dev wlan0 scan
```

### Windows: error al conectar o desconectar

Ejecuta WiFind como administrador o crea el perfil de red previamente desde Configuración de Windows.

### Linux: error al conectar o desconectar

Comprueba que NetworkManager esté activo y que tu usuario tenga permisos para gestionar conexiones WiFi (`nmcli device status`).

## Contribuir

Las contribuciones son bienvenidas. Abre un issue o pull request en:

**https://github.com/entreunosyceros/wifind**

## Licencia

Este proyecto se distribuye bajo licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## Autor

Desarrollado por [entreunosyceros](https://github.com/entreunosyceros).
