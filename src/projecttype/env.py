"""Carga variables de entorno desde `.env` en la raíz del proyecto."""

from __future__ import annotations

from pathlib import Path


def load_project_env(*, override: bool = False) -> Path | None:
    """Lee `.env` del proyecto si existe. No falla si falta python-dotenv o el archivo."""
    from .paths import PROJECT_ROOT

    env_path = PROJECT_ROOT / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None if not env_path.is_file() else env_path

    if env_path.is_file():
        load_dotenv(env_path, override=override)
    return env_path if env_path.is_file() else None
