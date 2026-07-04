"""PT-5 — publicar el tipo de proyecto clasificado al store canónico.

ProyectType es un *enriquecedor*: crea el atributo `tipo_proyecto` que NO existe
en las BBDD del BIP (EBI/RATE). El caso de uso del dueño ("quiero todos los
proyectos de ciclovía") se resuelve aquí: la cascada clasifica, y este módulo
escribe el resultado a la tabla `enr_tipo_proyecto` del store, donde SNI (u otro
consumidor) puede filtrar por tipo.

Escribe vía ``BipDataStore.upsert_dataframe`` (no destructivo): re-clasificar
solo actualiza las filas cuyo tipo cambió; nada se pierde.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import polars as pl

from proyecttype import __version__ as _pt_version
from proyecttype.inference_metadata import (
    inference_fields_for_row,
    prompt_version,
    taxonomy_hash,
)

# El código BIP aparece con distinto nombre según la etapa: "Codigo BIP" en el
# CSV de entrada, "codigo_bip" en el CSV de resultados. Se aceptan ambos.
_BIP_COL_CANDIDATES = ("codigo_bip", "Codigo BIP", "Código BIP", "EBI_CODIGO")
_TABLE = "enr_tipo_proyecto"

_INFERENCE_COLUMNS = (
    "nivel_asignacion",
    "confianza",
    "evidencia_resumen",
    "modelo",
    "prompt_version",
    "taxonomy_hash",
)


def _resolve_bip_column(columns: list[str]) -> str:
    """Devuelve el nombre real de la columna del código BIP, o lanza error claro."""
    for cand in _BIP_COL_CANDIDATES:
        if cand in columns:
            return cand
    raise ValueError(
        f"No se encontró la columna del código BIP. Buscadas: {_BIP_COL_CANDIDATES}. "
        f"Presentes: {columns}"
    )


def enricher_version() -> str:
    """Identificador de versión del enriquecedor para trazabilidad en el store."""
    return f"proyecttype@{_pt_version}"


def _ensure_inference_source_columns(resultados: pl.DataFrame) -> pl.DataFrame:
    """Completa columnas opcionales de evidencia si la cascada no las trajo."""
    out = resultados
    if "estado_final" not in out.columns:
        out = out.with_columns(
            pl.when(pl.col("tipo_final_id").is_not_null())
            .then(pl.lit("asignado"))
            .otherwise(pl.lit("sin_match"))
            .alias("estado_final")
        )
    optional = {
        "l1_estado": None,
        "l1_score": None,
        "l1_evidencia": "",
        "l2_estado": None,
        "l2_tipo_id": None,
        "l2_tipo_nombre": None,
        "l2_similitud": None,
        "l3_estado": None,
        "l3_confianza": None,
        "l3_razonamiento": "",
    }
    for col, default in optional.items():
        if col not in out.columns:
            out = out.with_columns(pl.lit(default).alias(col))
    return out


def _attach_inference_metadata(resultados: pl.DataFrame) -> pl.DataFrame:
    """Añade columnas SC-13 derivadas de la evidencia por nivel."""
    prompt_ver = prompt_version()
    tax_hash = taxonomy_hash()
    default_modelo = "n/a"
    if "_modelo_l3" in resultados.columns and resultados.height:
        default_modelo = str(resultados.get_column("_modelo_l3")[0] or "n/a")

    def _row_meta(row: dict[str, Any]) -> dict[str, Any]:
        return inference_fields_for_row(
            row,
            prompt_ver=prompt_ver,
            tax_hash=tax_hash,
            default_modelo=default_modelo,
        )

    meta = resultados.select(
        pl.struct(pl.all())
        .map_elements(
            _row_meta,
            return_dtype=pl.Struct(
                {
                    "nivel_asignacion": pl.Utf8,
                    "confianza": pl.Float64,
                    "evidencia_resumen": pl.Utf8,
                    "modelo": pl.Utf8,
                    "prompt_version": pl.Utf8,
                    "taxonomy_hash": pl.Utf8,
                }
            ),
        )
        .alias("_meta")
    ).unnest("_meta")
    return pl.concat([resultados, meta], how="horizontal")


def to_enrichment_frame(resultados: pl.DataFrame) -> pl.DataFrame:
    """Proyecta el DataFrame de la cascada al shape del contrato enr_tipo_proyecto.

    Selecciona y renombra las columnas relevantes, añade metadatos SC-13,
    ``enricher_version`` y descarta filas sin código BIP o sin tipo asignado.
    """
    from sni_commons.contracts import ENR_TIPO_PROYECTO_CONTRACT

    bip_col = _resolve_bip_column(resultados.columns)
    core_required = (
        "tipo_final_id",
        "tipo_final_nombre",
        "score_final",
        "nivel_final",
    )
    missing = [c for c in core_required if c not in resultados.columns]
    if missing:
        raise ValueError(
            f"El DataFrame de resultados no tiene las columnas de tipo esperadas: "
            f"{missing}. Presentes: {resultados.columns}"
        )

    prepared = _ensure_inference_source_columns(resultados)
    with_meta = _attach_inference_metadata(prepared)
    select_cols = [
        bip_col,
        "tipo_final_id",
        "tipo_final_nombre",
        "score_final",
        "nivel_final",
        *_INFERENCE_COLUMNS,
    ]
    rename = {bip_col: "EBI_CODIGO"}
    out = with_meta.select(select_cols).rename(rename)
    out = out.with_columns(
        pl.lit(enricher_version()).alias("enricher_version"),
        pl.col("EBI_CODIGO")
        .cast(pl.Utf8)
        .str.strip_chars()
        .str.split("-")
        .list.first()
        .alias("EBI_CODIGO"),
    )
    out = out.filter(
        pl.col("EBI_CODIGO").is_not_null()
        & (pl.col("EBI_CODIGO") != "")
        & pl.col("tipo_final_id").is_not_null()
    )
    ENR_TIPO_PROYECTO_CONTRACT.validate(out.columns, source="proyecttype.to_enrichment_frame")
    return out


def publish_to_store(
    resultados: pl.DataFrame,
    *,
    data_dir: str | Path | None = None,
    dry_run: bool = False,
    mark_missing: bool = True,
    source_label: str | None = None,
) -> Any:
    """Publica el tipo de proyecto al store (tabla ``enr_tipo_proyecto``).

    Args:
        resultados: DataFrame de salida de la cascada (con ``Codigo BIP``,
            ``tipo_final_id``, etc.).
        data_dir: directorio del store; si es None usa ``BIP_DATA_DIR``.
        dry_run: si True, calcula el diagnóstico sin escribir.
        mark_missing: si False, publish parcial (no toca claves ausentes del lote).
        source_label: origen en el ledger ``_loads``; default ``enricher_version()``.

    Returns:
        ``LoadDiagnostics`` del store (nuevas/cambiadas/sin-cambio/desaparecidas).
    """
    from sni_commons.contracts import ENR_TIPO_PROYECTO_CONTRACT
    from sni_commons.store import BipDataStore

    base = data_dir or os.environ.get("BIP_DATA_DIR")
    if not base:
        raise RuntimeError(
            "publish_to_store requiere data_dir o la variable BIP_DATA_DIR."
        )
    frame = to_enrichment_frame(resultados)
    store = BipDataStore(Path(base))
    source = source_label or enricher_version()
    return store.upsert_dataframe(
        _TABLE,
        frame,
        contract=ENR_TIPO_PROYECTO_CONTRACT,
        key_cols=["EBI_CODIGO"],
        source=source,
        dry_run=dry_run,
        writer=enricher_version(),  # ledger _loads (Store v1.1)
        mark_missing=mark_missing,
    )
