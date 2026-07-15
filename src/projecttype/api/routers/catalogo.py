"""Árbol del catálogo de tipos (sector → subsector → tipos) desde la taxonomía."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from projecttype.review.schemas import CatalogoResponse
from projecttype.review.store import TipoReviewStore

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])


def _store(request: Request) -> TipoReviewStore:
    store = request.app.state.review_store
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot no cargado.",
        )
    return store  # type: ignore[no-any-return]


@router.get("/arbol", response_model=CatalogoResponse)
def arbol(request: Request) -> CatalogoResponse:
    return _store(request).catalogo()
