"""Evaluación de clasificaciones contra etiquetado manual."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import polars as pl

from .paths import DEFAULT_EXPOST_DB
from .text_utils import normalize_tipo_name, pick_column


class NivelMatch(str, Enum):
    COINCIDENCIA_EXACTA = "Coincidencia exacta"
    COINCIDENCIA_PARCIAL = "Coincidencia parcial"
    DISCREPANCIA = "Discrepancia"
    SIN_CLASIFICACION_L1 = "Sin clasificación L1"
    SIN_ETIQUETA_MANUAL = "Sin etiqueta manual"


_ORDEN_NIVEL = {
    NivelMatch.DISCREPANCIA.value: 0,
    NivelMatch.COINCIDENCIA_PARCIAL.value: 1,
    NivelMatch.COINCIDENCIA_EXACTA.value: 2,
    NivelMatch.SIN_CLASIFICACION_L1.value: 3,
    NivelMatch.SIN_ETIQUETA_MANUAL.value: 4,
}


def _norm_tipo(value: str | None) -> str:
    if not value:
        return ""
    return normalize_tipo_name(value).upper()


def clasificar_match(
    tipo_python: str | None,
    tipo_manual: str | None,
    *,
    l1_estado: str | None = None,
) -> NivelMatch:
    manual = _norm_tipo(tipo_manual)
    python = _norm_tipo(tipo_python)

    if not manual:
        return NivelMatch.SIN_ETIQUETA_MANUAL

    if l1_estado in ("sin_match", "sin_taxonomia") or not python:
        return NivelMatch.SIN_CLASIFICACION_L1

    if manual == python:
        return NivelMatch.COINCIDENCIA_EXACTA

    if manual in python or python in manual:
        return NivelMatch.COINCIDENCIA_PARCIAL

    return NivelMatch.DISCREPANCIA


def _tipo_coincide(manual: str, candidato: str) -> bool:
    if not manual or not candidato:
        return False
    if manual == candidato:
        return True
    return manual in candidato or candidato in manual


def manual_en_tipos_l3(
    tipo_principal: str | None,
    tipos_secundarios: list[str] | None,
    tipo_manual: str | None,
) -> bool:
    """True si el manual coincide con el principal o algún secundario (PT-24 multi-hit)."""
    manual = _norm_tipo(tipo_manual)
    if not manual:
        return False
    principal = _norm_tipo(tipo_principal)
    if _tipo_coincide(manual, principal):
        return True
    for sec in tipos_secundarios or []:
        if _tipo_coincide(manual, _norm_tipo(sec)):
            return True
    return False


def parse_l3_secundarios_row(row: dict[str, Any]) -> list[str]:
    raw = row.get("l3_tipos_secundarios_nombres")
    if not raw:
        return []
    return [part.strip() for part in str(raw).split("|") if part.strip()]

def load_expost_manual(path: str | Path | None = None) -> pl.DataFrame:
    """Carga etiquetado manual desde ``informe_expost.duckdb`` (tabla ``ex_post``)."""
    import duckdb

    db_path = Path(path or DEFAULT_EXPOST_DB)
    if not db_path.is_file():
        raise FileNotFoundError(
            f"DuckDB de etiquetado no encontrado: {db_path}. "
            "Colocar informe_expost.duckdb en data/raw/ (gitignored)."
        )
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rel = con.execute(
            """
            SELECT
                split_part(trim(codigo_bip), '-', 1) AS codigo_bip,
                nombre,
                sector,
                subsector,
                tipo_proyecto,
                justificación_proyecto AS justificacion_proyecto,
                "descripción" AS descripcion,
                descriptor_1,
                descriptor_2,
                descriptor_3
            FROM ex_post
            WHERE tipo_proyecto IS NOT NULL AND trim(tipo_proyecto) != ''
            """
        )
        columns = [d[0] for d in rel.description]
        rows = rel.fetchall()
    finally:
        con.close()
    if not rows:
        return pl.DataFrame(schema={col: pl.Utf8 for col in columns})
    return pl.DataFrame([dict(zip(columns, row, strict=False)) for row in rows])


def load_submuestra(path: str | Path) -> pl.DataFrame:
    """Compatibilidad: delega al duckdb si el path es ``.duckdb``, si no error claro."""
    p = Path(path)
    if p.suffix.lower() == ".duckdb":
        return load_expost_manual(p)
    raise FileNotFoundError(
        f"Submuestra Excel deprecada ({p}). Usar {DEFAULT_EXPOST_DB} o load_expost_manual()."
    )


def build_revision_dataframe(
    resultados: pl.DataFrame,
    manual: pl.DataFrame,
    *,
    solo_asignado: bool = True,
) -> pl.DataFrame:
    """Construye DataFrame de revisión manual (L1 vs etiquetado manual)."""
    l1 = resultados.with_columns(
        pl.col("Codigo BIP").cast(pl.Utf8).str.strip_chars().alias("codigo_bip")
    )
    man = manual.with_columns(pl.col("codigo_bip").cast(pl.Utf8).str.strip_chars())

    man_columns = list(man.columns)
    justificacion_col = pick_column(man_columns, ("justificación_proyecto", "justificacion_proyecto"))
    descripcion_col = pick_column(man_columns, ("descripción", "descripcion"))

    man_select: list[pl.Expr | str] = [
        "codigo_bip",
        "nombre",
        "sector",
        "subsector",
        "tipo_proyecto",
    ]
    if justificacion_col:
        man_select.append(pl.col(justificacion_col).alias("_justificacion"))
    if descripcion_col:
        man_select.append(pl.col(descripcion_col).alias("_descripcion"))

    l1_select = [
        "codigo_bip",
        "l1_estado",
        "l1_tipo_nombre",
        "l1_score",
        "l1_margen",
        "l1_evidencia",
    ]
    l1_select = [c for c in l1_select if c in l1.columns]

    merged = man.select(man_select).join(l1.select(l1_select), on="codigo_bip", how="inner")

    if solo_asignado:
        merged = merged.filter(pl.col("l1_estado") == "asignado")

    merged = merged.filter(pl.col("tipo_proyecto").is_not_null())

    def _nivel_match(row: dict[str, Any]) -> str:
        return clasificar_match(
            row.get("l1_tipo_nombre"),
            row.get("tipo_proyecto"),
            l1_estado=row.get("l1_estado"),
        ).value

    merged = merged.with_columns(
        pl.struct(["l1_tipo_nombre", "tipo_proyecto", "l1_estado"])
        .map_elements(_nivel_match, return_dtype=pl.Utf8)
        .alias("nivel_match")
    )

    justificacion_expr = pl.col("_justificacion") if "_justificacion" in merged.columns else pl.lit("")
    descripcion_expr = pl.col("_descripcion") if "_descripcion" in merged.columns else pl.lit("")

    revision = merged.select(
        pl.col("codigo_bip"),
        pl.col("nombre"),
        pl.col("sector"),
        pl.col("subsector"),
        justificacion_expr.alias("justificacion"),
        descripcion_expr.alias("descripcion"),
        pl.col("l1_tipo_nombre").alias("tipo_proyecto_python"),
        pl.col("tipo_proyecto").alias("tipo_proyecto_manual"),
        pl.col("nivel_match"),
        pl.col("l1_estado"),
        pl.col("l1_score"),
        pl.col("l1_margen"),
        pl.col("l1_evidencia"),
    )

    return (
        revision.with_columns(
            pl.col("nivel_match")
            .replace_strict(_ORDEN_NIVEL, default=99)
            .alias("_ord")
        )
        .sort(["_ord", "l1_score"], descending=[False, True])
        .drop("_ord")
    )


def resumen_nivel_match(revision: pl.DataFrame) -> pl.DataFrame:
    total = revision.height
    return (
        revision.group_by("nivel_match")
        .len()
        .rename({"len": "cantidad"})
        .with_columns((pl.col("cantidad") / total * 100).round(1).alias("porcentaje"))
        .sort("cantidad", descending=True)
    )


def save_revision_excel(revision: pl.DataFrame, output: str | Path) -> Path:
    """Guarda revisión manual en Excel con hoja Resumen y formato condicional."""
    import xlsxwriter

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    resumen = resumen_nivel_match(revision)

    with xlsxwriter.Workbook(output) as workbook:
        revision.write_excel(workbook=workbook, worksheet="Revision")
        resumen.write_excel(workbook=workbook, worksheet="Resumen")

        worksheet = workbook.get_worksheet_by_name("Revision")
        col_idx = revision.columns.index("nivel_match")
        n_rows = revision.height

        fmt_exacta = workbook.add_format({"bg_color": "#C6EFCE"})
        fmt_parcial = workbook.add_format({"bg_color": "#FFEB9C"})
        fmt_discrep = workbook.add_format({"bg_color": "#FFC7CE"})

        worksheet.conditional_format(
            1,
            col_idx,
            n_rows,
            col_idx,
            {"type": "text", "criteria": "containing", "value": "exacta", "format": fmt_exacta},
        )
        worksheet.conditional_format(
            1,
            col_idx,
            n_rows,
            col_idx,
            {"type": "text", "criteria": "containing", "value": "parcial", "format": fmt_parcial},
        )
        worksheet.conditional_format(
            1,
            col_idx,
            n_rows,
            col_idx,
            {"type": "text", "criteria": "containing", "value": "Discrepancia", "format": fmt_discrep},
        )

        for i, col in enumerate(revision.columns):
            sample = revision.select(pl.col(col).cast(pl.Utf8).str.len_chars().quantile(0.9)).item()
            width = min(max(int(sample or 0), len(col)) + 2, 60)
            worksheet.set_column(i, i, width)

    return output
