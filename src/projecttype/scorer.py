"""Scoring determinístico Nivel 1 por keywords."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .composite import CompositeIndex
from .taxonomy import TipoProyecto
from .text_utils import contains_keyword, join_fields, normalize_text


class EstadoClasificacion(str, Enum):
    ASIGNADO = "asignado"
    AMBIGUO = "ambiguo"
    SIN_MATCH = "sin_match"
    SIN_TAXONOMIA = "sin_taxonomia"


@dataclass(frozen=True)
class ScorerConfig:
    strong_nombre: int = 3
    strong_desc: int = 2
    weak_any: int = 1
    exclusion_penalty: int = -5
    nombre_tipo_bonus: int = 4
    composite_components_bonus: int = 5
    composite_subset_penalty: int = -3
    min_margin: float = 2.0
    min_score: float = 1.0


@dataclass
class ScoreDetalle:
    keyword: str
    peso: int
    campo: str


@dataclass
class TipoScore:
    tipo: TipoProyecto
    score: float = 0.0
    detalles: list[ScoreDetalle] = field(default_factory=list)


@dataclass
class ProyectoTexto:
    nombre: str = ""
    descripcion: str = ""
    justificacion: str = ""
    descriptores: str = ""

    @property
    def nombre_norm(self) -> str:
        return normalize_text(self.nombre)

    @property
    def desc_just_norm(self) -> str:
        return normalize_text(join_fields(self.descripcion, self.justificacion))

    @property
    def all_norm(self) -> str:
        return normalize_text(
            join_fields(self.nombre, self.descripcion, self.justificacion, self.descriptores)
        )


@dataclass
class ResultadoClasificacion:
    estado: EstadoClasificacion
    tipo_id: str | None = None
    tipo_nombre: str | None = None
    score: float = 0.0
    score_segundo: float = 0.0
    margen: float = 0.0
    nivel: int = 1
    matches: list[ScoreDetalle] = field(default_factory=list)
    alternativas: list[str] = field(default_factory=list)
    sector_resuelto: str = ""
    subsector_resuelto: str = ""
    tipos_secundarios_ids: list[str] = field(default_factory=list)
    tipos_secundarios_nombres: list[str] = field(default_factory=list)
    multi_tipo: bool = False


def score_tipo(proyecto: ProyectoTexto, tipo: TipoProyecto, config: ScorerConfig) -> TipoScore:
    result = TipoScore(tipo=tipo)
    nombre = proyecto.nombre_norm
    desc_just = proyecto.desc_just_norm
    all_text = proyecto.all_norm

    if tipo.nombre_norm and contains_keyword(nombre, tipo.nombre_norm):
        result.score += config.nombre_tipo_bonus
        result.detalles.append(ScoreDetalle(tipo.nombre, config.nombre_tipo_bonus, "nombre_tipo"))

    for kw in tipo.keywords_fuertes_norm:
        if contains_keyword(nombre, kw):
            result.score += config.strong_nombre
            result.detalles.append(ScoreDetalle(kw, config.strong_nombre, "nombre"))
        elif contains_keyword(desc_just, kw):
            result.score += config.strong_desc
            result.detalles.append(ScoreDetalle(kw, config.strong_desc, "descripcion_justificacion"))

    for kw in tipo.keywords_debiles_norm:
        if contains_keyword(all_text, kw):
            result.score += config.weak_any
            result.detalles.append(ScoreDetalle(kw, config.weak_any, "cualquier_campo"))

    for kw in tipo.excluye_norm:
        if contains_keyword(all_text, kw):
            result.score += config.exclusion_penalty
            result.detalles.append(ScoreDetalle(kw, config.exclusion_penalty, "exclusion"))

    return result


def adjust_composite_scores(
    scores: list[TipoScore],
    proyecto: ProyectoTexto,
    config: ScorerConfig,
    composite_index: CompositeIndex | None,
) -> None:
    """Aplica bonificaciones/penalizaciones por tipos compuestos del subsector."""
    if composite_index is None:
        return

    by_id = {score.tipo.tipo_id: score for score in scores}
    for adjustment in composite_index.compute_adjustments(proyecto, config):
        score = by_id.get(adjustment.tipo_id)
        if score is None:
            continue
        score.score += adjustment.delta
        score.detalles.append(
            ScoreDetalle(adjustment.keyword, adjustment.delta, adjustment.campo)
        )


def clasificar_scores(
    scores: list[TipoScore],
    config: ScorerConfig,
    sector_resuelto: str = "",
    subsector_resuelto: str = "",
) -> ResultadoClasificacion:
    base = ResultadoClasificacion(
        estado=EstadoClasificacion.SIN_MATCH,
        sector_resuelto=sector_resuelto,
        subsector_resuelto=subsector_resuelto,
    )

    if not scores:
        base.estado = EstadoClasificacion.SIN_TAXONOMIA
        return base

    ranked = sorted(
        scores,
        key=lambda s: (s.score, len(s.tipo.nombre_norm), s.tipo.nombre_norm),
        reverse=True,
    )
    top = ranked[0]
    second_score = ranked[1].score if len(ranked) > 1 else 0.0
    margin = top.score - second_score

    base.score = top.score
    base.score_segundo = second_score
    base.margen = margin
    base.matches = top.detalles
    base.alternativas = [s.tipo.tipo_id for s in ranked[1:4] if s.score > 0]

    if top.score < config.min_score:
        base.estado = EstadoClasificacion.SIN_MATCH
        return base

    if margin >= config.min_margin:
        base.estado = EstadoClasificacion.ASIGNADO
        base.tipo_id = top.tipo.tipo_id
        base.tipo_nombre = top.tipo.nombre
        return base

    base.estado = EstadoClasificacion.AMBIGUO
    base.tipo_id = top.tipo.tipo_id
    base.tipo_nombre = top.tipo.nombre
    return base
