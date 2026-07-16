# Guía de contribución

Gracias por colaborar en **WiFind**.

Repositorio oficial: [https://github.com/entreunosyceros/wifind](https://github.com/entreunosyceros/wifind)

## Antes de empezar

- Lee el [README](README.md).
- Revisa issues abiertas: [https://github.com/entreunosyceros/wifind/issues](https://github.com/entreunosyceros/wifind/issues)
- Consulta [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) y [SECURITY.md](SECURITY.md).

## Entorno de desarrollo

Requisitos: Python 3.10+, PyQt6, NumPy, SciPy, Matplotlib, Jinja2.

```bash
git clone https://github.com/entreunosyceros/wifind.git
cd wifind
python3 run_app.py
```

Arranque manual:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

## Qué contribuciones son útiles

- Correcciones de bugs en escaneo WiFi, intensidad, mapa de calor, dispositivos LAN o exportación.
- Mejoras en UX de PyQt6.
- Mejoras de rendimiento y estabilidad.
- Documentación y ejemplos de uso.

## Estilo y alcance de cambios

- Mantén PRs pequeñas y enfocadas.
- Respeta el estilo existente del código.
- Textos de UI/documentación en español claro.
- Evita mezclar refactors grandes con fixes funcionales.
- No incluyas secretos, datos privados de red ni rutas personales.

## Pull Requests

1. Crea una rama desde `main`.
2. Explica qué cambia y por qué.
3. Describe cómo lo probaste (pasos manuales y/o comandos).
4. Si cambias comportamiento visible, actualiza README/manual.
5. Usa la plantilla de PR: `.github/pull_request_template.md`.

## Issues

- Bug report / feature request: usa las plantillas de `.github/ISSUE_TEMPLATE/`.
- Seguridad: sigue [SECURITY.md](SECURITY.md).

## Licencia

Al contribuir, aceptas que tu aportación se publique bajo la licencia del proyecto ([MIT](LICENSE)).
