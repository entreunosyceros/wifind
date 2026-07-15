#!/usr/bin/env python3
"""Punto de entrada de WiFind — mapa de calor e intensidad WiFi."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DIRECTORIO_PROYECTO = Path(__file__).resolve().parent
ARCHIVO_REQUISITOS = DIRECTORIO_PROYECTO / "requirements.txt"
PAQUETES_REQUERIDOS = ("PyQt6", "matplotlib", "numpy", "jinja2")


def obtener_directorio_venv() -> Path:
    """
    Directorio del entorno virtual.

    - Desarrollo: DIRECTORIO_PROYECTO/.venv
    - Instalación de solo lectura: ~/.local/share/wifind/.venv
    - WIFIND_VENV: ruta explícita
    """
    override = os.environ.get("WIFIND_VENV")
    if override:
        return Path(override)
    local = DIRECTORIO_PROYECTO / ".venv"
    if os.access(DIRECTORIO_PROYECTO, os.W_OK):
        return local
    data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    return data_home / "wifind" / ".venv"


def obtener_python_venv() -> Path:
    directorio_venv = obtener_directorio_venv()
    if sys.platform == "win32":
        return directorio_venv / "Scripts" / "python.exe"
    return directorio_venv / "bin" / "python"


def ejecutando_en_venv() -> bool:
    if not obtener_directorio_venv().exists():
        return False
    return Path(sys.prefix).resolve() == obtener_directorio_venv().resolve()


def crear_venv() -> None:
    directorio_venv = obtener_directorio_venv()
    directorio_venv.parent.mkdir(parents=True, exist_ok=True)
    print(f"Creando entorno virtual en {directorio_venv} …")
    subprocess.run(
        [sys.executable, "-m", "venv", str(directorio_venv)],
        check=True,
        cwd=DIRECTORIO_PROYECTO,
    )
    print("Entorno virtual creado.")


def asegurar_venv() -> Path:
    python_venv = obtener_python_venv()
    if not python_venv.exists():
        crear_venv()
        python_venv = obtener_python_venv()
    if not python_venv.exists():
        raise RuntimeError("No se pudo crear el entorno virtual.")
    return python_venv


def instalar_dependencias(python_venv: Path) -> None:
    print("Instalando dependencias en el entorno virtual …")
    subprocess.run(
        [str(python_venv), "-m", "pip", "install", "-q", "--upgrade", "pip"],
        check=True,
        cwd=DIRECTORIO_PROYECTO,
    )
    if ARCHIVO_REQUISITOS.exists():
        cmd = [
            str(python_venv),
            "-m",
            "pip",
            "install",
            "-q",
            "-r",
            str(ARCHIVO_REQUISITOS),
        ]
    else:
        cmd = [str(python_venv), "-m", "pip", "install", "-q", *PAQUETES_REQUERIDOS]
    subprocess.run(cmd, check=True, cwd=DIRECTORIO_PROYECTO)
    print("Dependencias instaladas correctamente.")


def iniciar_app() -> int:
    from wifind.ui.ventana_principal import MENSAJE_CIERRE_CTRL_C, ejecutar_app

    try:
        ejecutar_app()
    except KeyboardInterrupt:
        print(MENSAJE_CIERRE_CTRL_C, flush=True)
        return 0
    return 0


def principal() -> int:
    os.chdir(DIRECTORIO_PROYECTO)
    if str(DIRECTORIO_PROYECTO) not in sys.path:
        sys.path.insert(0, str(DIRECTORIO_PROYECTO))

    if ejecutando_en_venv():
        try:
            return iniciar_app()
        except Exception as exc:
            import traceback

            print(f"Error al iniciar WiFind: {exc}", file=sys.stderr)
            traceback.print_exc()
            return 1

    try:
        python_venv = asegurar_venv()
        instalar_dependencias(python_venv)

        print("Iniciando WiFind …")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(DIRECTORIO_PROYECTO)
        os.environ.update(env)
        argv = [str(python_venv), str(__file__), *sys.argv[1:]]
        os.execv(str(python_venv), argv)
        return 1

    except subprocess.CalledProcessError as exc:
        print(f"Error al preparar el entorno: {exc}", file=sys.stderr)
        print(
            "\nSugerencias:\n"
            "- Comprueba tu conexión a internet.\n"
            "- Instala manualmente: .venv/bin/pip install -r requirements.txt\n"
            "- Recrea el entorno: borra ~/.local/share/wifind/.venv "
            "(o .venv en el proyecto) y vuelve a ejecutar.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print(
            "\nWiFind: interrupción por teclado (Ctrl+C) durante la preparación.\n"
            "No se llegó a abrir la aplicación.\n",
            flush=True,
        )
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(principal())
