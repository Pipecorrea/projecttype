"""PT-6 — input de la cascada directamente del store canónico (CONSULTAS_EBI).

Cierra el ciclo store→store del enriquecedor: en vez de partir de un CSV local
(`data/raw/base_datos_extracto.csv`), los proyectos se leen del store y se
proyectan al shape que espera la cascada L1→L2→L3:

==================  =======================================================
Columna cascada     Origen en CONSULTAS_EBI
==================  =======================================================
``Codigo BIP``      ``EBI_CODIGO`` (canónico del store: sin dígito verificador)
``NOMBRE``          ``EBI_NOMBRE``
``SECTOR``          ``SEC_CLAVE`` → nombre vía ``sni_commons.reference``
``SUBSECTOR``       ``SBS_CLAVE`` → nombre vía ``sni_commons.reference``
``descripción``     ``EBI_DESCRIPCION``
``justificacion_proyecto``  ``EBI_JUSTIFICACION``
``descriptor_1..3`` vacíos (no existen en EBI; la cascada los tolera)
==================  =======================================================

CONSULTAS_EBI trae una fila por (proyecto, solicitud): se deduplica a una fila
por proyecto quedándose con la solicitud más reciente (SOL_CLAVE máxima).
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl
from sni_commons.reference import descripcion_sector, descripcion_subsector

_EBI_TABLE = "CONSULTAS_EBI"
_NEEDED_COLS = (
    "EBI_CODIGO",
    "SOL_CLAVE",
    "EBI_NOMBRE",
    "SEC_CLAVE",
    "SBS_CLAVE",
    "EBI_DESCRIPCION",
    "EBI_JUSTIFICACION",
)


def load_cascade_input_from_store(
    data_dir: str | Path | None = None,
    *,
    limit: int | None = None,
) -> pl.DataFrame:
    """Lee CONSULTAS_EBI del store y devuelve el input de la cascada.

    Args:
        data_dir: directorio del store; si es None usa ``BIP_DATA_DIR``.
        limit: si se indica, recorta a los primeros N proyectos (pilotos).
    """
    from sni_commons.store import BipDataStore

    base = data_dir or os.environ.get("BIP_DATA_DIR")
    if not base:
        raise RuntimeError(
            "load_cascade_input_from_store requiere data_dir o la variable BIP_DATA_DIR."
        )
    store = BipDataStore(Path(base))
    df: pl.DataFrame = store.read_polars(_EBI_TABLE)

    missing = [c for c in _NEEDED_COLS if c not in df.columns]
    if missing:
        raise RuntimeError(
            f"CONSULTAS_EBI en el store no tiene las columnas {missing}. "
            f"¿Se cargó con `bip-data load --table ebi`?"
        )
    df = df.select(list(_NEEDED_COLS))

    # Una fila por proyecto: la solicitud más reciente gana.
    df = (
        df.with_columns(pl.col("SOL_CLAVE").cast(pl.Int64, strict=False).alias("_sol"))
        .sort("_sol", descending=True, nulls_last=True)
        .unique(subset=["EBI_CODIGO"], keep="first")
        .drop("_sol")
    )

    out = df.select(
        pl.col("EBI_CODIGO").cast(pl.Utf8).str.strip_chars().alias("Codigo BIP"),
        pl.col("EBI_NOMBRE").cast(pl.Utf8).fill_null("").alias("NOMBRE"),
        pl.col("SEC_CLAVE")
        .cast(pl.Utf8)
        .map_elements(lambda c: descripcion_sector(c) or "", return_dtype=pl.Utf8)
        .alias("SECTOR"),
        pl.col("SBS_CLAVE")
        .cast(pl.Utf8)
        .map_elements(lambda c: descripcion_subsector(c) or "", return_dtype=pl.Utf8)
        .alias("SUBSECTOR"),
        pl.col("EBI_JUSTIFICACION").cast(pl.Utf8).fill_null("").alias("justificacion_proyecto"),
        pl.col("EBI_DESCRIPCION").cast(pl.Utf8).fill_null("").alias("descripción"),
        pl.lit("").alias("descriptor_1"),
        pl.lit("").alias("descriptor_2"),
        pl.lit("").alias("descriptor_3"),
    ).sort("Codigo BIP")

    if limit is not None:
        out = out.head(limit)
    return out
