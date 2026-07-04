"""PT-7 — anti-join contra clasificaciones vigentes en el store."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from sni_commons.reference import to_store_key

_ENR_TABLE = "enr_tipo_proyecto"


@dataclass(frozen=True, slots=True)
class PendingSplit:
    pendientes: pl.DataFrame
    saltados: pl.DataFrame


def filter_pending(
    input_df: pl.DataFrame,
    *,
    data_dir: str | Path | None = None,
    tax_hash: str,
    prompt_ver: str,
    enricher_ver: str,
) -> PendingSplit:
    """Separa proyectos pendientes de clasificar vs ya vigentes con mismos metadatos."""
    from sni_commons.store import BipDataStore, StoreError

    base = data_dir or os.environ.get("BIP_DATA_DIR")
    if not base:
        raise RuntimeError(
            "filter_pending requiere data_dir o la variable BIP_DATA_DIR."
        )
    store = BipDataStore(Path(base))
    try:
        enr = store.read_polars(_ENR_TABLE, only_present=True)
    except StoreError:
        return PendingSplit(pendientes=input_df, saltados=input_df.head(0))

    needed = {"EBI_CODIGO", "taxonomy_hash", "prompt_version", "enricher_version"}
    if not needed.issubset(set(enr.columns)):
        return PendingSplit(pendientes=input_df, saltados=input_df.head(0))

    done = (
        enr.filter(
            (pl.col("taxonomy_hash") == tax_hash)
            & (pl.col("prompt_version") == prompt_ver)
            & (pl.col("enricher_version") == enricher_ver)
        )
        .select(pl.col("EBI_CODIGO").cast(pl.Utf8).str.strip_chars().alias("_ebi"))
        .unique()
    )
    done_set = set(done["_ebi"].to_list())

    inp = input_df.with_columns(
        pl.col("Codigo BIP")
        .map_elements(lambda c: to_store_key(str(c)), return_dtype=pl.Utf8)
        .alias("_ebi")
    )
    pending_mask = ~pl.col("_ebi").is_in(done_set)
    pendientes = inp.filter(pending_mask).drop("_ebi")
    saltados = inp.filter(~pending_mask).drop("_ebi")
    return PendingSplit(pendientes=pendientes, saltados=saltados)
