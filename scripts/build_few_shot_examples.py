#!/usr/bin/env python3
"""Genera ejemplos few-shot desde submuestra manual (casos donde L1 falló)."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from projecttype.few_shot_mining import mine_from_files, write_few_shot_yaml
from projecttype.paths import (
    DEFAULT_EXPOST_DB,
    DEFAULT_OUTPUT_CASCADE_CSV,
    DEFAULT_TAXONOMY,
    PROJECT_ROOT,
)

PROMPTS_DIR = PROJECT_ROOT / "data" / "prompts"
DEFAULT_MINED = PROMPTS_DIR / "few_shot_mined.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mineria few-shot: proyectos con etiqueta manual donde L1 no acertó."
    )
    parser.add_argument(
        "--resultados",
        default=str(DEFAULT_OUTPUT_CASCADE_CSV),
        help="CSV resultados L1+L2",
    )
    parser.add_argument("--manual", default=str(DEFAULT_EXPOST_DB))
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    parser.add_argument(
        "--output",
        default=str(DEFAULT_MINED),
        help="YAML de ejemplos minados",
    )
    parser.add_argument("--max-per-subsector", type=int, default=2)
    parser.add_argument("--max-total", type=int, default=50)
    args = parser.parse_args()

    examples = mine_from_files(
        resultados_path=Path(args.resultados),
        manual_path=Path(args.manual),
        taxonomy_path=Path(args.taxonomy),
        max_per_subsector=args.max_per_subsector,
        max_total=args.max_total,
    )

    if not examples:
        print("No se encontraron candidatos para minería.")
        return 1

    out_path = write_few_shot_yaml(examples, Path(args.output))
    print(f"Ejemplos minados: {len(examples)}")
    print(f"Guardado en: {out_path}")

    print("\nPor nivel_match_l1:")
    for nivel, count in Counter(ex.nivel_match_l1 for ex in examples).most_common():
        print(f"  {nivel:25s} {count:4d}")

    print("\nPor subsector (top 10):")
    for sub, count in Counter(ex.subsector for ex in examples).most_common(10):
        print(f"  {sub[:45]:45s} {count:3d}")

    print("\nLos ejemplos minados se cargan automáticamente junto a few_shot_examples.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
