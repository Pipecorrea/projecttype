"""Pipeline batch con Polars para clasificación Nivel 1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from .classifier_l1 import ClassifierL1
from .scorer import ResultadoClasificacion, ScorerConfig


def _resultado_to_dict(result: ResultadoClasificacion) -> dict[str, Any]:
    return {
        "l1_estado": result.estado.value,
        "l1_tipo_id": result.tipo_id,
        "l1_tipo_nombre": result.tipo_nombre,
        "l1_score": result.score,
        "l1_score_segundo": result.score_segundo,
        "l1_margen": result.margen,
        "l1_nivel": result.nivel,
        "l1_evidencia": _format_evidencia(result),
        "l1_alternativas": "|".join(result.alternativas),
        "sector_resuelto": result.sector_resuelto,
        "subsector_resuelto": result.subsector_resuelto,
    }


def _format_evidencia(result: ResultadoClasificacion) -> str:
    if not result.matches:
        return ""
    parts = [f"{m.campo}:{m.keyword}(+{m.peso})" for m in result.matches[:8]]
    return "; ".join(parts)


def classify_dataframe(
    df: pl.DataFrame,
    classifier: ClassifierL1,
    *,
    sector_col: str = "SECTOR",
    subsector_col: str = "SUBSECTOR",
    nombre_col: str = "NOMBRE",
    descripcion_col: str = "descripción",
    justificacion_col: str = "justificacion_proyecto",
    descriptor_cols: tuple[str, ...] = ("descriptor_1", "descriptor_2", "descriptor_3"),
) -> pl.DataFrame:
    """Clasifica un DataFrame Polars fila a fila.

    Para cientos de miles de filas, Polars mantiene I/O eficiente;
    el scoring es O(filas × tipos_subsector) con tipos_subsector ~5-15.
    """

    def _classify_row(row: dict[str, Any]) -> dict[str, Any]:
        result = classifier.classify_row(
            sector=row.get(sector_col),
            subsector=row.get(subsector_col),
            nombre=row.get(nombre_col),
            descripcion=row.get(descripcion_col),
            justificacion=row.get(justificacion_col),
            descriptor_1=row.get(descriptor_cols[0]),
            descriptor_2=row.get(descriptor_cols[1]),
            descriptor_3=row.get(descriptor_cols[2]),
        )
        return _resultado_to_dict(result)

    schema = {
        "l1_estado": pl.Utf8,
        "l1_tipo_id": pl.Utf8,
        "l1_tipo_nombre": pl.Utf8,
        "l1_score": pl.Float64,
        "l1_score_segundo": pl.Float64,
        "l1_margen": pl.Float64,
        "l1_nivel": pl.Int64,
        "l1_evidencia": pl.Utf8,
        "l1_alternativas": pl.Utf8,
        "sector_resuelto": pl.Utf8,
        "subsector_resuelto": pl.Utf8,
    }

    resultados = (
        df.select(
            pl.struct(pl.all())
            .map_elements(_classify_row, return_dtype=pl.Struct(schema))
            .alias("_l1")
        )
        .unnest("_l1")
    )

    return pl.concat([df, resultados], how="horizontal")


def save_results(
    df: pl.DataFrame,
    output_csv: str | Path,
    *,
    output_excel: str | Path | None = None,
    write_excel: bool = True,
) -> tuple[Path, Path | None]:
    """Guarda resultados en CSV y, opcionalmente, Excel."""
    csv_path = Path(output_csv)
    df.write_csv(csv_path)

    if not write_excel:
        return csv_path, None

    excel_path = Path(output_excel) if output_excel else csv_path.with_suffix(".xlsx")
    df.write_excel(excel_path, worksheet="Resultados")
    return csv_path, excel_path


def classify_csv(
    input_path: str | Path,
    output_path: str | Path,
    taxonomy_path: str | Path,
    *,
    output_excel: str | Path | None = None,
    write_excel: bool = True,
    config: ScorerConfig | None = None,
    separator: str = ",",
) -> tuple[pl.DataFrame, Path, Path | None]:
    classifier = ClassifierL1.from_yaml(taxonomy_path, config=config)
    df = pl.read_csv(input_path, separator=separator, infer_schema_length=1000, ignore_errors=True)
    result = classify_dataframe(df, classifier)
    csv_path, excel_path = save_results(
        result, output_path, output_excel=output_excel, write_excel=write_excel
    )
    return result, csv_path, excel_path
