# Política de seguridad

## Versiones con soporte

| Versión | Soportada |
| ------- | --------- |
| `main`  | ✅ |
| ramas antiguas | ⚠️ esfuerzo razonable |

## Alcance

WiFind es una aplicación de escritorio (PyQt6) para escaneo y análisis de redes WiFi. En seguridad, nos preocupan especialmente:

- Exposición accidental de credenciales o secretos.
- Lectura/escritura de archivos fuera de rutas esperadas.
- Dependencias de Python con vulnerabilidades conocidas.
- Comportamientos inseguros en funciones de red local (escaneo LAN, parsing de comandos del sistema).

## Reportar vulnerabilidades

1. No abras issues públicas con detalles explotables.
2. Usa GitHub Security Advisories:
   - [https://github.com/entreunosyceros/wifind/security/advisories/new](https://github.com/entreunosyceros/wifind/security/advisories/new)
3. Si no puedes usar Advisories, abre un issue con título `SECURITY (sin detalles)` para solicitar canal privado.

Incluye:

- Componente afectado.
- Pasos de reproducción.
- Impacto estimado.
- Versión/commit.

## Buenas prácticas para usuarios

- Usa siempre código y releases del repo oficial:
  - [https://github.com/entreunosyceros/wifind](https://github.com/entreunosyceros/wifind)
- Mantén dependencias actualizadas.
- No compartas capturas/logs con SSID, BSSID, IPs privadas o credenciales sin anonimizar.
