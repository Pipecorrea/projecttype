"""Sirve el build de la SPA (`web/dist`) desde `projecttype serve` (mismo origen que /api)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_RESERVED_EXACT = frozenset({"health", "docs", "redoc", "openapi.json"})


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def mount_spa(app: FastAPI, dist_dir: Path) -> bool:
    """Monta la SPA en la raíz cuando `dist_dir/index.html` existe."""
    dist = dist_dir.resolve()
    index = (dist / "index.html").resolve()
    if not index.is_file():
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/") or full_path in _RESERVED_EXACT:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and _is_within(candidate, dist) and candidate != index:
            return FileResponse(candidate)
        # index.html nunca se cachea: garantiza que un build nuevo se tome siempre.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
