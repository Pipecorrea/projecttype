#!/usr/bin/env python3
"""CLI para clasificación Nivel 1 sobre CSV de proyectos BIP."""

from __future__ import annotations

import argparse
from collections import Counter

from proyecttype.paths import DEFAULT_INPUT_CSV, DEFAULT_OUTPUT_CSV, DEFAULT_TAXONOMY  # noqa: E402
from proyecttype.pipeline import classify_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clasificador Nivel 1 de tipos de proyecto BIP (keywords + scoring)."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=str(DEFAULT_INPUT_CSV),
        help="CSV de entrada con proyectos BIP",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_OUTPUT_CSV),
        help="CSV de salida con columnas l1_*",
    )
    parser.add_argument(
        "--output-excel",
        default=None,
        help="Ruta del Excel de salida (default: mismo nombre que --output con .xlsx)",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="No generar archivo Excel",
    )
    parser.add_argument(
        "--taxonomy",
        "-t",
        default=str(DEFAULT_TAXONOMY),
        help="YAML de taxonomía",
    )
    parser.add_argument(
        "--min-margin",
        type=float,
        default=2.0,
        help="Margen mínimo sobre el segundo lugar para asignación confiable",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=1.0,
        help="Score mínimo para considerar una asignación",
    )
    args = parser.parse_args()

    from proyecttype.scorer import ScorerConfig

    config = ScorerConfig(min_margin=args.min_margin, min_score=args.min_score)
    result, csv_path, excel_path = classify_csv(
        args.input,
        args.output,
        args.taxonomy,
        output_excel=args.output_excel,
        write_excel=not args.no_excel,
        config=config,
    )

    estados = Counter(result["l1_estado"].to_list())
    total = len(result)

    print(f"Proyectos procesados: {total}")
    print("\nDistribución por estado:")
    for estado, count in estados.most_common():
        pct = 100.0 * count / total if total else 0
        print(f"  {estado:15s} {count:5d}  ({pct:5.1f}%)")

    asignados = result.filter(result["l1_estado"] == "asignado")
    if len(asignados):
        print(f"\nScore promedio (asignados): {asignados['l1_score'].mean():.2f}")
        print(f"Margen promedio (asignados): {asignados['l1_margen'].mean():.2f}")

    print(f"\nResultados guardados en: {csv_path}")
    if not args.no_excel:
        print(f"Excel guardado en: {excel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
