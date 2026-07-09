#!/usr/bin/env python3
"""Exporta índice de tipos compuestos detectados en la taxonomía."""

from __future__ import annotations

import polars as pl

from projecttype.composite import CompositeIndex, parse_tipo_components
from projecttype.paths import DEFAULT_TAXONOMY, TAXONOMY_DIR
from projecttype.taxonomy import Taxonomia
from projecttype.text_utils import normalize_tipo_name


def main() -> int:
    tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)
    rows: list[dict] = []

    for (sector, subsector), tipos in tax._by_sector_subsector.items():
        sibling_names = frozenset(normalize_tipo_name(t.nombre) for t in tipos)
        index = CompositeIndex.from_tipos(tipos)

        for relation in index.relations:
            components = relation.components
            rows.append(
                {
                    "sector": sector,
                    "subsector": subsector,
                    "tipo_compuesto": relation.composite.nombre,
                    "tipo_id": relation.composite.tipo_id,
                    "partes_and": " | ".join(components.and_parts),
                    "grupos_or": " ; ".join(" / ".join(g) for g in components.or_groups),
                    "subtipos": " | ".join(t.nombre for t in relation.subsets),
                }
            )

        for tipo in tipos:
            parts = parse_tipo_components(tipo.nombre, sibling_names)
            if parts.is_composite and not any(
                r.composite.tipo_id == tipo.tipo_id for r in index.relations
            ):
                rows.append(
                    {
                        "sector": sector,
                        "subsector": subsector,
                        "tipo_compuesto": tipo.nombre,
                        "tipo_id": tipo.tipo_id,
                        "partes_and": " | ".join(parts.and_parts),
                        "grupos_or": " ; ".join(" / ".join(g) for g in parts.or_groups),
                        "subtipos": "",
                    }
                )

    output = TAXONOMY_DIR / "composites_index.csv"
    pl.DataFrame(rows).write_csv(output)
    print(f"Relaciones compuestas: {len(rows)}")
    print(f"Guardado en: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
