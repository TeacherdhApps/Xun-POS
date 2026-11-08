#!/usr/bin/env python3
"""Modos de uso y rutas de datos de Xun-POS.

Modos:
    production  Usuarios reales con contraseña; datos en XDG_DATA_HOME/xun-pos
    kiosk       Sin login; misma carpeta de datos que producción
    demo        admin/password y datos de ejemplo en xun-pos/demo
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

APP_NAME = "xun-pos"
MODES = ("production", "kiosk", "demo")
MODE_ENV = "XUN_POS_MODE"

LEGACY_FILES = (
    ".credentials",
    "productos.csv",
    "ventas.csv",
    "flujo_caja.csv",
    "settings.json",
)

CSV_HEADERS = {
    "ventas.csv": "fecha_hora,codigo,nombre,cantidad,precio_unitario,total\n",
    "flujo_caja.csv": "fecha_hora,tipo,monto,concepto\n",
}


def app_dir() -> Path:
    """Directory where the application scripts live."""
    return Path(__file__).resolve().parent


def _xdg_dir(env_var: str, fallback: str) -> Path:
    base = os.environ.get(env_var) or os.path.join(Path.home(), fallback)
    return Path(base) / APP_NAME


def config_dir() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", ".config")


def config_path() -> Path:
    return config_dir() / "config.json"


def data_home() -> Path:
    return _xdg_dir("XDG_DATA_HOME", os.path.join(".local", "share"))


def get_mode(default: str | None = None) -> str | None:
    """Return the active mode: env override, saved config, or default."""
    env_mode = os.environ.get(MODE_ENV)
    if env_mode in MODES:
        return env_mode
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        mode = data.get("mode")
        if mode in MODES:
            return mode
    except (OSError, ValueError):
        pass
    return default


def save_mode(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"Modo inválido: {mode}")
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    path = config_path()
    path.write_text(
        json.dumps({"mode": mode}, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(path, 0o600)


def data_dir(mode: str | None = None) -> Path:
    """Data directory for a mode; demo has its own folder."""
    active = mode or get_mode("production")
    base = data_home()
    return base / "demo" if active == "demo" else base


def db_path(mode: str | None = None) -> Path:
    return data_dir(mode) / "xun.db"


def credentials_path(mode: str | None = None) -> Path:
    return data_dir(mode) / ".credentials"


def ensure_data_dir(mode: str | None = None) -> Path:
    directory = data_dir(mode)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    return directory


def copy_legacy_data(mode: str | None = None) -> list[str]:
    """Copy old data files from the app directory on first run.

    Demo mode never copies real data.
    """
    active = mode or get_mode("production")
    if active == "demo":
        return []

    destination = ensure_data_dir(active)
    copied = []
    for name in LEGACY_FILES:
        source = app_dir() / name
        target = destination / name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass
            copied.append(name)
    return copied


def seed_demo_data() -> Path:
    """Create the demo data directory with sample files."""
    directory = ensure_data_dir("demo")

    for source_name, target_name in (
        ("productos.ejemplo.csv", "productos.csv"),
        ("settings.ejemplo.json", "settings.json"),
    ):
        source = app_dir() / source_name
        target = directory / target_name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)

    for csv_name, header in CSV_HEADERS.items():
        target = directory / csv_name
        if not target.exists():
            target.write_text(header, encoding="utf-8")

    return directory
