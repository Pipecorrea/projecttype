"""Clasificador Nivel 1: reglas determinísticas por keywords."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .aliases import resolve_sector_subsector
from .scorer import (
    EstadoClasificacion,
    ProyectoTexto,
    ResultadoClasificacion,
    ScorerConfig,
    adjust_composite_scores,
    clasificar_scores,
    score_tipo,
)
from .taxonomy import Taxonomia
from .text_utils import join_fields, normalize_key


class ClassifierL1:
    def __init__(
        self,
        taxonomia: Taxonomia,
        config: ScorerConfig | None = None,
    ) -> None:
        self.taxonomia = taxonomia
        self.config = config or ScorerConfig()

    @classmethod
    def from_yaml(
        cls,
        taxonomy_path: str | Path,
        config: ScorerConfig | None = None,
    ) -> ClassifierL1:
        return cls(Taxonomia.from_yaml(taxonomy_path), config=config)

    def classify_row(
        self,
        *,
        sector: str | None,
        subsector: str | None,
        nombre: str | None = None,
        descripcion: str | None = None,
        justificacion: str | None = None,
        descriptor_1: str | None = None,
        descriptor_2: str | None = None,
        descriptor_3: str | None = None,
    ) -> ResultadoClasificacion:
        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        tipos = self.taxonomia.tipos_para(sector, subsector)

        if not tipos:
            return ResultadoClasificacion(
                estado=EstadoClasificacion.SIN_TAXONOMIA,
                sector_resuelto=sector_res,
                subsector_resuelto=subsector_res,
            )

        proyecto = ProyectoTexto(
            nombre=nombre or "",
            descripcion=descripcion or "",
            justificacion=justificacion or "",
            descriptores=join_fields(descriptor_1, descriptor_2, descriptor_3),
        )

        scores = [score_tipo(proyecto, tipo, self.config) for tipo in tipos]
        composite_index = self.taxonomia.composite_index_para(sector, subsector)
        adjust_composite_scores(scores, proyecto, self.config, composite_index)
        return clasificar_scores(scores, self.config, sector_res, subsector_res)

    def classify_dict(self, row: dict[str, Any]) -> ResultadoClasificacion:
        return self.classify_row(
            sector=row.get("SECTOR") or row.get("sector"),
            subsector=row.get("SUBSECTOR") or row.get("subsector"),
            nombre=row.get("NOMBRE") or row.get("nombre"),
            descripcion=row.get("descripción") or row.get("descripcion") or row.get("DESCRIPCION"),
            justificacion=row.get("justificacion_proyecto")
            or row.get("justificacion")
            or row.get("JUSTIFICACION"),
            descriptor_1=row.get("descriptor_1") or row.get("DESCRIPTOR_1"),
            descriptor_2=row.get("descriptor_2") or row.get("DESCRIPTOR_2"),
            descriptor_3=row.get("descriptor_3") or row.get("DESCRIPTOR_3"),
        )

    def lookup_key(self, sector: str | None, subsector: str | None) -> tuple[str, str]:
        return (
            normalize_key(resolve_sector_subsector(sector, subsector)[0]),
            normalize_key(resolve_sector_subsector(sector, subsector)[1]),
        )
