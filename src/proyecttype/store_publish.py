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

# El código BIP aparece con distinto nombre según la etapa: "Codigo BIP" en el
# CSV de entrada, "codigo_bip" en el CSV de resultados. Se aceptan ambos.
_BIP_COL_CANDIDATES = ("codigo_bip", "Codigo BIP", "Código BIP", "EBI_CODIGO")
_TABLE = "enr_tipo_proyecto"

# Columnas de tipo (cascada) que se publican; el BIP se resuelve aparte.
_TYPE_COLUMNS = ("tipo_final_id", "tipo_final_nombre", "score_final", "nivel_final")


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


def to_enrichment_frame(resultados: pl.DataFrame) -> pl.DataFrame:
    """Proyecta el DataFrame de la cascada al shape del contrato enr_tipo_proyecto.

    Selecciona y renombra las columnas relevantes, añade ``enricher_version`` y
    descarta filas sin código BIP o sin tipo asignado (no aportan al enriquecimiento).
    """
    bip_col = _resolve_bip_column(resultados.columns)
    missing = [c for c in _TYPE_COLUMNS if c not in resultados.columns]
    if missing:
        raise ValueError(
            f"El DataFrame de resultados no tiene las columnas de tipo esperadas: "
            f"{missing}. Presentes: {resultados.columns}"
        )
    rename = {bip_col: "EBI_CODIGO"}
    out = resultados.select([bip_col, *_TYPE_COLUMNS]).rename(rename)
    out = out.with_columns(
        # Código BIP canónico del store: sin el dígito verificador "-N".
        # ProyectType trae "30069417-0"; CONSULTAS_EBI usa "30069417". Sin esta
        # normalización el JOIN enr × EBI da 0 filas (joinabilidad = razón de ser
        # del store). split antes del primer '-'.
        pl.col("EBI_CODIGO").cast(pl.Utf8).str.strip_chars().str.split("-").list.first().alias("EBI_CODIGO"),
        pl.lit(enricher_version()).alias("enricher_version"),
    )
    # Solo filas con BIP y con un tipo asignado.
    out = out.filter(
        pl.col("EBI_CODIGO").is_not_null()
        & (pl.col("EBI_CODIGO") != "")
        & pl.col("tipo_final_id").is_not_null()
    )
    return out


def publish_to_store(
    resultados: pl.DataFrame,
    *,
    data_dir: str | Path | None = None,
    dry_run: bool = False,
) -> Any:
    """Publica el tipo de proyecto al store (tabla ``enr_tipo_proyecto``).

    Args:
        resultados: DataFrame de salida de la cascada (con ``Codigo BIP``,
            ``tipo_final_id``, etc.).
        data_dir: directorio del store; si es None usa ``BIP_DATA_DIR``.
        dry_run: si True, calcula el diagnóstico sin escribir.

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
    return store.upsert_dataframe(
        _TABLE,
        frame,
        contract=ENR_TIPO_PROYECTO_CONTRACT,
        key_cols=["EBI_CODIGO"],
        source=enricher_version(),
        dry_run=dry_run,
        writer=enricher_version(),  # ledger _loads (Store v1.1)
    )
