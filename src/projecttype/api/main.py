"""API HTTP de la UI HITL de ProjectType (PT-19)."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from projecttype import __version__
from projecttype.api.routers import catalogo as catalogo_router
from projecttype.api.routers import config as config_router
from projecttype.api.routers import manual as manual_router
from projecttype.api.routers import review as review_router
from projecttype.api.static import mount_spa
from projecttype.paths import DEFAULT_L3_CACHE_JSONL, DEFAULT_TAXONOMY, PROJECT_ROOT
from projecttype.review.store import TipoReviewStore

WEB_DIST = PROJECT_ROOT / "web" / "dist"
DEFAULT_VERDICTS = PROJECT_ROOT / "data" / "review" / "veredictos_tipo.jsonl"

# Puertos: serve 8788, Vite dev 5176 (evita colisión con OBSRATE 8777/5175).
DEFAULT_PORT = 8788
_VITE_DEV_ORIGINS = ["http://127.0.0.1:5176", "http://localhost:5176"]


def create_app(
    *,
    taxonomy_path: Path | None = None,
    verdicts_path: Path | None = None,
    data_dir: Path | None = None,
    l3_cache_path: Path | None = None,
    load_snapshot: bool = True,
) -> FastAPI:
    app = FastAPI(
        title="ProjectType Review UI",
        version=__version__,
        description="Revisión y clasificación manual del tipo de proyecto (HITL, D-19).",
    )
    tax = taxonomy_path or DEFAULT_TAXONOMY
    verdicts = verdicts_path or DEFAULT_VERDICTS
    cache = l3_cache_path if l3_cache_path is not None else DEFAULT_L3_CACHE_JSONL
    app.state.data_dir = data_dir
    app.state.l3_cache_path = cache
    app.state.review_store = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_VITE_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _no_store_api(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict[str, object]:
        store = app.state.review_store
        summary = store.summary() if store is not None else None
        return {
            "status": "ok",
            "version": __version__,
            "snapshot_loaded": store is not None,
            "total_clasificados": summary.total_clasificados if summary else 0,
            "revisados": summary.revisados if summary else 0,
            "taxonomy_hash": summary.taxonomy_hash if summary else "",
        }

    app.include_router(review_router.router)
    app.include_router(manual_router.router)
    app.include_router(catalogo_router.router)
    app.include_router(config_router.router)

    if load_snapshot:
        app.state.review_store = TipoReviewStore.open(
            taxonomy_path=tax,
            verdicts_path=verdicts,
            data_dir=data_dir,
            l3_cache_path=cache,
        )

    mount_spa(app, WEB_DIST)
    return app


app = create_app(load_snapshot=False)


def run() -> None:
    """Entry point de `projecttype serve` (arranca uvicorn con snapshot cargado)."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="projecttype serve", description="UI HITL de ProjectType.")
    parser.add_argument("--host", default=os.environ.get("PROJECTTYPE_UI_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("PROJECTTYPE_UI_PORT", str(DEFAULT_PORT)))
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="Store (default BIP_DATA_DIR).")
    parser.add_argument("--reload", action="store_true", help="Autoreload (solo desarrollo).")
    args = parser.parse_args()

    global app
    app = create_app(data_dir=args.data_dir, load_snapshot=True)
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
