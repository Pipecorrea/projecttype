#!/usr/bin/env python3
"""Genera Excel de revisión manual: L1 vs etiquetado manual."""

from __future__ import annotations

import argparse
from collections import Counter

import polars as pl  # noqa: E402

from projecttype.evaluation import (
    build_revision_dataframe,
    load_expost_manual,
    save_revision_excel,
)
from projecttype.paths import (
    DEFAULT_EXPOST_DB,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_REVISION_XLSX,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera Excel de revisión manual L1 vs etiquetado manual."
    )
    parser.add_argument(
        "--resultados",
        "-r",
        default=str(DEFAULT_OUTPUT_CSV),
        help="CSV con resultados L1",
    )
    parser.add_argument(
        "--manual",
        "-m",
        default=str(DEFAULT_EXPOST_DB),
        help="DuckDB con etiquetado manual (ex_post)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_REVISION_XLSX),
        help="Excel de salida para revisión",
    )
    parser.add_argument(
        "--include-ambiguo",
        action="store_true",
        help="Incluir también proyectos con l1_estado=ambiguo",
    )
    args = parser.parse_args()

    resultados = pl.read_csv(args.resultados, infer_schema_length=1000, ignore_errors=True)
    manual = load_expost_manual(args.manual)
    revision = build_revision_dataframe(
        resultados,
        manual,
        solo_asignado=not args.include_ambiguo,
    )

    output = save_revision_excel(revision, args.output)

    print(f"Proyectos en revisión: {revision.height}")
    print("\nDistribución nivel_match:")
    for nivel, count in Counter(revision["nivel_match"].to_list()).most_common():
        pct = 100 * count / revision.height
        print(f"  {nivel:25s} {count:5d}  ({pct:5.1f}%)")
    print(f"\nGuardado en: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
