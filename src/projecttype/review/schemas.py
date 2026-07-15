"""Contratos de la UI HITL de ProjectType (revisión + clasificación manual).

`RevisionTipoRecord` es la línea persistida en `data/review/veredictos_tipo.jsonl`
(commiteada, política de datos derivados). El resto son DTOs de la API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

Origen = Literal["l1", "l2", "l3", "residual", "manual"]


class Veredicto(str, Enum):
    """Decisión humana sobre la propuesta del sistema para un BIP."""

    ACEPTADO = "aceptado"
    CORREGIDO = "corregido"
    SIN_TIPO_APLICABLE = "sin_tipo_aplicable"
    NO_EVALUABLE = "no_evaluable"


VEREDICTO_LABELS: dict[Veredicto, str] = {
    Veredicto.ACEPTADO: "Aceptado",
    Veredicto.CORREGIDO: "Corregido",
    Veredicto.SIN_TIPO_APLICABLE: "Sin tipo aplicable",
    Veredicto.NO_EVALUABLE: "No evaluable",
}


class RevisionTipoRecord(BaseModel):
    """Un veredicto humano persistido (última decisión por EBI gana)."""

    ebi_codigo: str = Field(description="Canónico D-6 (sin dígito verificador)")
    # Contexto denormalizado (para que el JSONL sea auditable sin el store)
    nombre: str = ""
    sector: str = ""
    subsector: str = ""
    descripcion: str = ""
    justificacion: str = ""
    # Propuesta del sistema al momento de revisar
    origen: Origen = "manual"
    tipo_propuesto_id: str | None = None
    tipo_propuesto_nombre: str | None = None
    confianza_sistema: float | None = None
    evidencia: str = ""
    cot: str = Field(default="", description="Chain-of-thought del L3 (si aplica)")
    # Veredicto
    veredicto: Veredicto
    tipo_final_id: str | None = None
    tipo_final_nombre: str | None = None
    notas: str = ""
    revisor: str = Field(min_length=1)
    revisado_en: datetime
    # Snapshot de la era (para saber contra qué prompt/taxonomía se decidió)
    taxonomy_hash: str = ""
    prompt_version: str = ""
    modelo: str = ""
    enricher_version: str = ""
    # Marcas del loop de salida (PT-21)
    exportado_golden_en: datetime | None = None
    publicado_en: datetime | None = None


# ── DTOs de API ────────────────────────────────────────────────────


class ReviewSummary(BaseModel):
    total_clasificados: int = Field(description="Filas del store con propuesta del sistema")
    revisados: int
    pendientes: int
    por_origen: dict[str, int] = Field(default_factory=dict)
    por_veredicto: dict[str, int] = Field(default_factory=dict)
    taxonomy_hash: str = ""
    prompt_version: str = ""
    store_writer: str | None = None
    store_actualizado: str | None = None


class QueueItem(BaseModel):
    ebi_codigo: str
    nombre: str
    sector: str
    subsector: str
    origen: Origen
    tipo_propuesto_id: str | None
    tipo_propuesto_nombre: str | None
    confianza_sistema: float | None
    revisado: bool
    veredicto: Veredicto | None = None
    revisor: str | None = None


class QueueResponse(BaseModel):
    items: list[QueueItem]
    total: int
    offset: int
    limit: int


class ItemDetail(BaseModel):
    ebi_codigo: str
    nombre: str
    sector: str
    subsector: str
    descripcion: str
    justificacion: str
    origen: Origen
    tipo_propuesto_id: str | None
    tipo_propuesto_nombre: str | None
    confianza_sistema: float | None
    evidencia: str
    cot: str
    tipos_secundarios: list[str] = Field(default_factory=list)
    review: RevisionTipoRecord | None = None
    index: int = 0
    total: int = 0


class SaveVerdictRequest(BaseModel):
    veredicto: Veredicto
    tipo_final_id: str | None = None
    notas: str = ""
    revisor: str = Field(min_length=1)


# ── Clasificación manual ───────────────────────────────────────────


class SubsectorCobertura(BaseModel):
    sector: str
    subsector: str
    n_tipos: int = Field(description="Tipos en la taxonomía para este subsector")
    n_clasificados: int = Field(description="BIP del store ya clasificados en este subsector")
    n_pendientes: int = Field(description="BIP del store sin clasificar en este subsector")


class SubsectoresResponse(BaseModel):
    items: list[SubsectorCobertura]
    total: int


class ManualPendienteItem(BaseModel):
    ebi_codigo: str
    nombre: str
    sector: str
    subsector: str
    descripcion: str
    justificacion: str


class ManualPendientesResponse(BaseModel):
    items: list[ManualPendienteItem]
    total: int
    offset: int
    limit: int


# ── Catálogo (árbol de tipos) ──────────────────────────────────────


class CatalogoTipo(BaseModel):
    tipo_id: str
    nombre: str
    definicion: str = ""


class CatalogoSubsector(BaseModel):
    subsector: str
    tipos: list[CatalogoTipo]


class CatalogoSector(BaseModel):
    sector: str
    subsectores: list[CatalogoSubsector]


class CatalogoResponse(BaseModel):
    sectores: list[CatalogoSector]
    n_tipos: int
    n_subsectores: int
    taxonomy_hash: str
