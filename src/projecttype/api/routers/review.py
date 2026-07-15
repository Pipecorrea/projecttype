"""Cola de revisión: propuestas del sistema para validar/corregir."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from projecttype.review.schemas import (
    ItemDetail,
    QueueResponse,
    ReviewSummary,
    RevisionTipoRecord,
    SaveVerdictRequest,
)
from projecttype.review.store import TipoReviewStore

router = APIRouter(prefix="/api/review", tags=["review"])


def _store(request: Request) -> TipoReviewStore:
    store = request.app.state.review_store
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot no cargado.",
        )
    return store  # type: ignore[no-any-return]


@router.get("/summary", response_model=ReviewSummary)
def summary(request: Request) -> ReviewSummary:
    return _store(request).summary()


@router.get("/queue", response_model=QueueResponse)
def queue(
    request: Request,
    origen: str | None = Query(None),
    subsector: str | None = Query(None),
    estado: str | None = Query(None, description="pendiente | revisado"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> QueueResponse:
    return _store(request).queue(
        origen=origen, subsector=subsector, estado=estado, offset=offset, limit=limit
    )


@router.get("/item/{ebi}", response_model=ItemDetail)
def item(request: Request, ebi: str) -> ItemDetail:
    detail = _store(request).item(ebi)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sin propuesta para {ebi}.")
    return detail


@router.post("/item/{ebi}/verdict", response_model=RevisionTipoRecord)
def save_verdict(request: Request, ebi: str, body: SaveVerdictRequest) -> RevisionTipoRecord:
    return _store(request).save_verdict(ebi, body)


@router.post("/reload", response_model=ReviewSummary)
def reload(request: Request) -> ReviewSummary:
    store = _store(request)
    store.reload(
        data_dir=request.app.state.data_dir,
        l3_cache_path=request.app.state.l3_cache_path,
    )
    return store.summary()
