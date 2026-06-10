"""Pipeline batch L1 → L2 → L3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from .classifier_cascade import ClassifierCascade
from .classifier_l3 import L3Config
from .embeddings import L2Config
from .l3_cache import L3ResultCache, entry_to_result
from .pipeline import classify_dataframe, save_results
from .progress import BatchProgress, ProgressCallback
from .scorer import EstadoClasificacion, ResultadoClasificacion, ScorerConfig


def _l2_to_dict(result: ResultadoClasificacion | None) -> dict[str, Any]:
    if result is None:
        return {
            "l2_estado": None,
            "l2_tipo_id": None,
            "l2_tipo_nombre": None,
            "l2_similitud": None,
            "l2_similitud_segundo": None,
            "l2_margen": None,
            "l2_nivel": None,
        }
    return {
        "l2_estado": result.estado.value,
        "l2_tipo_id": result.tipo_id,
        "l2_tipo_nombre": result.tipo_nombre,
        "l2_similitud": result.score,
        "l2_similitud_segundo": result.score_segundo,
        "l2_margen": result.margen,
        "l2_nivel": result.nivel,
    }


def _l3_to_dict(
    result: ResultadoClasificacion | None,
    razonamiento: str = "",
) -> dict[str, Any]:
    if result is None:
        return {
            "l3_estado": None,
            "l3_tipo_id": None,
            "l3_tipo_nombre": None,
            "l3_confianza": None,
            "l3_razonamiento": None,
            "l3_nivel": None,
        }
    return {
        "l3_estado": result.estado.value,
        "l3_tipo_id": result.tipo_id,
        "l3_tipo_nombre": result.tipo_nombre,
        "l3_confianza": result.score,
        "l3_razonamiento": razonamiento or None,
        "l3_nivel": result.nivel,
    }


def _final_to_dict(result: ResultadoClasificacion) -> dict[str, Any]:
    return {
        "estado_final": result.estado.value,
        "tipo_final_id": result.tipo_id,
        "tipo_final_nombre": result.tipo_nombre,
        "nivel_final": result.nivel,
        "score_final": result.score,
        "margen_final": result.margen,
    }


def _row_to_l1_result(row: dict[str, Any]) -> ResultadoClasificacion:
    return ResultadoClasificacion(
        estado=EstadoClasificacion(row["l1_estado"]),
        tipo_id=row.get("l1_tipo_id"),
        tipo_nombre=row.get("l1_tipo_nombre"),
        score=float(row.get("l1_score") or 0.0),
        score_segundo=float(row.get("l1_score_segundo") or 0.0),
        margen=float(row.get("l1_margen") or 0.0),
        nivel=1,
        sector_resuelto=row.get("sector_resuelto") or "",
        subsector_resuelto=row.get("subsector_resuelto") or "",
    )


def _interim_final(row: dict[str, Any], l2_overrides: dict[int, ResultadoClasificacion]) -> ResultadoClasificacion:
    idx = row["_row_idx"]
    if idx in l2_overrides:
        return l2_overrides[idx]
    return _row_to_l1_result(row)


def _is_residual(result: ResultadoClasificacion) -> bool:
    return result.estado in ClassifierCascade.RESIDUAL


def classify_cascade_dataframe(
    df: pl.DataFrame,
    cascade: ClassifierCascade,
    *,
    sector_col: str = "SECTOR",
    subsector_col: str = "SUBSECTOR",
    nombre_col: str = "NOMBRE",
    descripcion_col: str = "descripción",
    justificacion_col: str = "justificacion_proyecto",
    descriptor_cols: tuple[str, ...] = ("descriptor_1", "descriptor_2", "descriptor_3"),
    l3_limit: int | None = None,
    l3_progress_interval: int = 1,
    l3_progress: ProgressCallback | None = None,
    l3_progress_file: Path | None = None,
    l3_cache_path: Path | None = None,
    l3_use_cache: bool = True,
    l3_model: str = "",
) -> pl.DataFrame:
    with_l1 = classify_dataframe(
        df,
        cascade.l1,
        sector_col=sector_col,
        subsector_col=subsector_col,
        nombre_col=nombre_col,
        descripcion_col=descripcion_col,
        justificacion_col=justificacion_col,
        descriptor_cols=descriptor_cols,
    ).with_row_index("_row_idx")

    n = with_l1.height
    l2_rows: list[dict[str, Any]] = [_l2_to_dict(None) for _ in range(n)]
    l3_rows: list[dict[str, Any]] = [_l3_to_dict(None) for _ in range(n)]
    l2_overrides: dict[int, ResultadoClasificacion] = {}
    l3_overrides: dict[int, ResultadoClasificacion] = {}

    l1_residual_idx = (
        with_l1.filter(pl.col("l1_estado").is_in(["ambiguo", "sin_match"]))
        .select("_row_idx")
        .to_series()
        .to_list()
    )

    if l1_residual_idx:
        residual_df = with_l1.filter(pl.col("_row_idx").is_in(l1_residual_idx))
        for keys, group_df in residual_df.group_by(["sector_resuelto", "subsector_resuelto"]):
            sector_res, subsector_res = keys
            row_dicts = group_df.to_dicts()
            indices = [row["_row_idx"] for row in row_dicts]
            l2_results = cascade.l2.classify_rows_batch(
                row_dicts,
                sector=sector_res,
                subsector=subsector_res,
            )
            for idx, l2_res in zip(indices, l2_results, strict=False):
                l2_rows[idx] = _l2_to_dict(l2_res)
                if l2_res.estado == EstadoClasificacion.ASIGNADO:
                    l2_overrides[idx] = l2_res

    if cascade.l3:
        l3_candidate_idx: list[int] = []
        interim_rows = with_l1.to_dicts()
        # Índice idx -> fila: evita un filtro O(n) sobre el DataFrame por cada
        # candidato L3 (antes era cuadrático en el nº de residuales).
        rows_by_idx = {r["_row_idx"]: r for r in interim_rows}
        for row in interim_rows:
            idx = row["_row_idx"]
            interim = _interim_final(row, l2_overrides)
            if _is_residual(interim):
                l3_candidate_idx.append(idx)

        if l3_candidate_idx:
            l3_cache: L3ResultCache | None = None
            if l3_use_cache and l3_cache_path is not None:
                l3_cache = L3ResultCache(l3_cache_path, model=l3_model or "gemini-2.5-flash")

            uncached_idx: list[int] = []
            for idx in l3_candidate_idx:
                row = rows_by_idx[idx]
                codigo = str(row.get("Codigo BIP") or "")
                entry = l3_cache.get(codigo) if l3_cache and codigo else None
                if entry is not None:
                    l3_res, razon = entry_to_result(
                        entry,
                        sector_res=row.get("sector_resuelto") or "",
                        subsector_res=row.get("subsector_resuelto") or "",
                    )
                    l3_rows[idx] = _l3_to_dict(l3_res, razon)
                    if l3_res.estado == EstadoClasificacion.ASIGNADO:
                        l3_overrides[idx] = l3_res
                else:
                    uncached_idx.append(idx)

            if l3_limit is not None:
                uncached_idx = uncached_idx[:l3_limit]

            l3_done = sum(
                1 for idx in l3_candidate_idx if l3_rows[idx]["l3_estado"] is not None
            )
            l3_total = l3_done + len(uncached_idx)

            progress = l3_progress
            if progress is None and l3_total > 0:
                progress = BatchProgress(
                    total=l3_total,
                    label="L3",
                    interval=max(1, l3_progress_interval),
                    log_path=l3_progress_file,
                ).as_callback()
            if progress and l3_done:
                progress(l3_done, l3_total, None)

            if uncached_idx:
                l3_df = (
                    with_l1.filter(pl.col("_row_idx").is_in(uncached_idx))
                    .sort("_row_idx")
                )
                for row in l3_df.to_dicts():
                    idx = row["_row_idx"]
                    sector_res = row.get("sector_resuelto") or ""
                    subsector_res = row.get("subsector_resuelto") or ""
                    l2 = l2_rows[idx]
                    codigo = str(row.get("Codigo BIP") or "")
                    l3_res, razon = cascade.l3.classify_row(
                        sector=row.get("SECTOR"),
                        subsector=row.get("SUBSECTOR"),
                        nombre=row.get("NOMBRE"),
                        descripcion=row.get("descripción"),
                        justificacion=row.get("justificacion_proyecto"),
                        descriptor_1=row.get("descriptor_1"),
                        descriptor_2=row.get("descriptor_2"),
                        descriptor_3=row.get("descriptor_3"),
                        l1_tipo_id=row.get("l1_tipo_id"),
                        l1_tipo_nombre=row.get("l1_tipo_nombre"),
                        l1_estado=row.get("l1_estado"),
                        l1_score=row.get("l1_score"),
                        l1_margen=row.get("l1_margen"),
                        l1_alternativas=row.get("l1_alternativas"),
                        l2_tipo_id=l2["l2_tipo_id"],
                        l2_tipo_nombre=l2["l2_tipo_nombre"],
                        l2_estado=l2["l2_estado"],
                        l2_similitud=l2["l2_similitud"],
                        l2_margen=l2["l2_margen"],
                        codigo_bip=codigo or None,
                    )
                    l3_rows[idx] = _l3_to_dict(l3_res, razon)
                    if l3_res.estado == EstadoClasificacion.ASIGNADO:
                        l3_overrides[idx] = l3_res
                    if l3_cache and codigo and not (razon or "").startswith("Error LLM"):
                        l3_cache.put(codigo, l3_res, razon)
                        l3_cache.api_calls += 1
                        if l3_cache.api_calls % 5 == 0:
                            l3_cache.save()
                    l3_done += 1
                    if progress:
                        progress(l3_done, l3_total, codigo or None)

            if l3_cache is not None:
                l3_cache.save()
                if l3_cache.hits or l3_cache.api_calls:
                    print(
                        f"L3 caché: {l3_cache.hits} desde disco, "
                        f"{l3_cache.api_calls} llamadas API nuevas "
                        f"({l3_cache.size} total en {l3_cache.path})"
                    )

    l2_df = pl.DataFrame(
        l2_rows,
        schema={
            "l2_estado": pl.Utf8,
            "l2_tipo_id": pl.Utf8,
            "l2_tipo_nombre": pl.Utf8,
            "l2_similitud": pl.Float64,
            "l2_similitud_segundo": pl.Float64,
            "l2_margen": pl.Float64,
            "l2_nivel": pl.Int64,
        },
    )
    l3_df = pl.DataFrame(
        l3_rows,
        schema={
            "l3_estado": pl.Utf8,
            "l3_tipo_id": pl.Utf8,
            "l3_tipo_nombre": pl.Utf8,
            "l3_confianza": pl.Float64,
            "l3_razonamiento": pl.Utf8,
            "l3_nivel": pl.Int64,
        },
    )
    merged = pl.concat([with_l1, l2_df, l3_df], how="horizontal")

    def _final_fields(row: dict[str, Any]) -> dict[str, Any]:
        idx = row["_row_idx"]
        if idx in l3_overrides:
            return _final_to_dict(l3_overrides[idx])
        if idx in l2_overrides:
            return _final_to_dict(l2_overrides[idx])
        return _final_to_dict(_row_to_l1_result(row))

    finals = merged.select(
        pl.struct(pl.all())
        .map_elements(
            _final_fields,
            return_dtype=pl.Struct(
                {
                    "estado_final": pl.Utf8,
                    "tipo_final_id": pl.Utf8,
                    "tipo_final_nombre": pl.Utf8,
                    "nivel_final": pl.Int64,
                    "score_final": pl.Float64,
                    "margen_final": pl.Float64,
                }
            ),
        )
        .alias("_final")
    ).unnest("_final")

    return pl.concat([merged.drop("_row_idx"), finals], how="horizontal")


def classify_cascade_csv(
    input_path: str | Path,
    output_path: str | Path,
    taxonomy_path: str | Path,
    *,
    output_excel: str | Path | None = None,
    write_excel: bool = True,
    l1_config: ScorerConfig | None = None,
    l2_config: L2Config | None = None,
    l3_config: L3Config | None = None,
    cache_dir: Path | None = None,
    enable_l3: bool = False,
    l3_mock: bool = False,
    l3_limit: int | None = None,
    l3_progress_interval: int = 1,
    l3_progress_file: Path | None = None,
    l3_cache_path: Path | None = None,
    l3_use_cache: bool = True,
    separator: str = ",",
) -> tuple[pl.DataFrame, Path, Path | None]:
    cascade = ClassifierCascade.from_yaml(
        taxonomy_path,
        l1_config=l1_config,
        l2_config=l2_config,
        l3_config=l3_config,
        cache_dir=cache_dir,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
    )
    l3_model = ""
    if l3_config and l3_config.llm:
        l3_model = l3_config.llm.resolved_model()
    df = pl.read_csv(input_path, separator=separator, infer_schema_length=1000, ignore_errors=True)
    result = classify_cascade_dataframe(
        df,
        cascade,
        l3_limit=l3_limit,
        l3_progress_interval=l3_progress_interval,
        l3_progress_file=l3_progress_file,
        l3_cache_path=l3_cache_path if enable_l3 else None,
        l3_use_cache=l3_use_cache,
        l3_model=l3_model,
    )
    csv_path, excel_path = save_results(
        result, output_path, output_excel=output_excel, write_excel=write_excel
    )
    return result, csv_path, excel_path
