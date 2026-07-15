"""Clasificación manual: subsectores por cobertura + proyectos pendientes.

Usable **sin** la tanda pagada de L3: opera sobre CONSULTAS_EBI + la taxonomía.
Guardar un veredicto manual reutiliza el mismo store JSONL que la revisión.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from projecttype.review.schemas import (
    ManualPendientesResponse,
    RevisionTipoRecord,
    SaveVerdictRequest,
    SubsectoresResponse,
)
from projecttype.review.store import TipoReviewStore

router = APIRouter(prefix="/api/manual", tags=["manual"])


def _store(request: Request) -> TipoReviewStore:
    store = request.app.state.review_store
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot no cargado.",
        )
    return store  # type: ignore[no-any-return]


@router.get("/subsectores", response_model=SubsectoresResponse)
def subsectores(request: Request) -> SubsectoresResponse:
    return _store(request).subsectores()


@router.get("/pendientes", response_model=ManualPendientesResponse)
def pendientes(
    request: Request,
    sector: str | None = Query(None),
    subsector: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> ManualPendientesResponse:
    return _store(request).pendientes(
        sector=sector, subsector=subsector, offset=offset, limit=limit
    )


@router.post("/clasificar/{ebi}", response_model=RevisionTipoRecord)
def clasificar(request: Request, ebi: str, body: SaveVerdictRequest) -> RevisionTipoRecord:
    """Clasifica manualmente un BIP sin propuesta previa (mismo store de veredictos)."""
    return _store(request).save_verdict(ebi, body)
