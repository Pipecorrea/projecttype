"""Clasificador Nivel 2: embeddings + similitud coseno."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from proyecttype.taxonomy import TipoProyecto

from pathlib import Path

from .aliases import resolve_sector_subsector
from .embeddings import L2Config, cosine_top2, cosine_top2_batch, encode_texts
from .scorer import EstadoClasificacion, ProyectoTexto, ResultadoClasificacion
from .taxonomy import Taxonomia
from .text_utils import join_fields
from .tipo_embedder import TipoEmbeddingStore, build_project_text


def _result_from_similarity(
    tipos: list[TipoProyecto],
    sim1: float,
    sim2: float,
    idx1: int,
    idx2: int,
    config: L2Config,
    sector_res: str,
    subsector_res: str,
) -> ResultadoClasificacion:
    base = ResultadoClasificacion(
        estado=EstadoClasificacion.SIN_MATCH,
        sector_resuelto=sector_res,
        subsector_resuelto=subsector_res,
        nivel=2,
    )
    if not tipos or idx1 < 0:
        return base

    top = tipos[idx1]
    margin = sim1 - sim2
    base.score = sim1
    base.score_segundo = sim2
    base.margen = margin
    base.tipo_id = top.tipo_id
    base.tipo_nombre = top.nombre
    base.alternativas = [tipos[idx2].tipo_id] if idx2 >= 0 and idx2 < len(tipos) else []

    if sim1 < config.min_similarity:
        return base

    if margin >= config.min_margin:
        base.estado = EstadoClasificacion.ASIGNADO
        return base

    base.estado = EstadoClasificacion.AMBIGUO
    return base


class ClassifierL2:
    def __init__(
        self,
        taxonomia: Taxonomia,
        embedding_store: TipoEmbeddingStore,
        config: L2Config | None = None,
    ) -> None:
        self.taxonomia = taxonomia
        self.store = embedding_store
        self.config = config or embedding_store.config

    @classmethod
    def from_yaml(
        cls,
        taxonomy_path: str | Path,
        *,
        config: L2Config | None = None,
        cache_dir: Path | None = None,
    ) -> ClassifierL2:
        path = Path(taxonomy_path)
        cfg = config or L2Config()
        store = TipoEmbeddingStore.from_yaml(path, config=cfg, cache_dir=cache_dir)
        return cls(store.taxonomia, store, cfg)

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
        proyecto: ProyectoTexto | None = None,
    ) -> ResultadoClasificacion:
        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        tipos_raw = self.taxonomia.tipos_para(sector, subsector)
        tipos, matrix = self.store.matrix_for_tipos(tipos_raw)

        if not tipos:
            return ResultadoClasificacion(
                estado=EstadoClasificacion.SIN_TAXONOMIA,
                sector_resuelto=sector_res,
                subsector_resuelto=subsector_res,
                nivel=2,
            )

        if proyecto is None:
            proyecto = ProyectoTexto(
                nombre=nombre or "",
                descripcion=descripcion or "",
                justificacion=justificacion or "",
                descriptores=join_fields(descriptor_1, descriptor_2, descriptor_3),
            )

        text = build_project_text(
            nombre=proyecto.nombre,
            descripcion=proyecto.descripcion,
            justificacion=proyecto.justificacion,
            descriptores=proyecto.descriptores,
            max_chars=self.config.max_project_chars,
        )
        query = encode_texts([text], model_name=self.config.model_name, batch_size=1)[0]
        sim1, sim2, idx1, idx2 = cosine_top2(query, matrix)
        return _result_from_similarity(
            tipos, sim1, sim2, idx1, idx2, self.config, sector_res, subsector_res
        )

    def classify_rows_batch(
        self,
        rows: list[dict[str, Any]],
        *,
        sector: str | None,
        subsector: str | None,
    ) -> list[ResultadoClasificacion]:
        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        tipos_raw = self.taxonomia.tipos_para(sector, subsector)
        tipos, matrix = self.store.matrix_for_tipos(tipos_raw)

        if not tipos:
            return [
                ResultadoClasificacion(
                    estado=EstadoClasificacion.SIN_TAXONOMIA,
                    sector_resuelto=sector_res,
                    subsector_resuelto=subsector_res,
                    nivel=2,
                )
                for _ in rows
            ]

        texts = [
            build_project_text(
                nombre=row.get("nombre") or row.get("NOMBRE") or "",
                descripcion=row.get("descripcion") or row.get("descripción") or "",
                justificacion=row.get("justificacion")
                or row.get("justificacion_proyecto")
                or "",
                descriptores=join_fields(
                    row.get("descriptor_1"),
                    row.get("descriptor_2"),
                    row.get("descriptor_3"),
                ),
                max_chars=self.config.max_project_chars,
            )
            for row in rows
        ]
        queries = encode_texts(
            texts,
            model_name=self.config.model_name,
            batch_size=self.config.batch_size,
        )
        sim1, sim2, idx1, idx2 = cosine_top2_batch(queries, matrix)
        results: list[ResultadoClasificacion] = []
        for i in range(len(rows)):
            results.append(
                _result_from_similarity(
                    tipos,
                    float(sim1[i]),
                    float(sim2[i]),
                    int(idx1[i]),
                    int(idx2[i]),
                    self.config,
                    sector_res,
                    subsector_res,
                )
            )
        return results

# El re-export de CascadeResult/ClassifierCascade se eliminó: creaba un ciclo
# l2→cascade→l2 que dependía del orden de import. Importar desde
# proyecttype.classifier_cascade (o el paquete raíz).
