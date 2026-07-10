#!/usr/bin/env python3
"""Convierte informe_expost.duckdb → golden-set sni_commons.eval (PT-17)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import duckdb

from projecttype.golden_split import assign_dev_holdout_tags, split_summary
from projecttype.paths import DEFAULT_EXPOST_DB, DEFAULT_GOLDEN, EVAL_DIR

# Rótulos del informe ex post → nombre canónico en taxonomia_tipos_proyecto.yaml
TIPO_ALIASES: dict[str, str] = {
    "Gimnasio Estandar": "GIMNASIO ESTANDARD",
    "Casetas Sanitarias/alcantarillado/agua Potable/energia": (
        "CASETAS SANITARIAS /ALCANTARILLADO/AGUA POTABLE/ENERGIA"
    ),
    "Centro Cumplimiento Penitenciario (ccp)": (
        "CENTRO DE CUMPLIMIENTO PENITENCIARIO (CCP)"
    ),
    "Pequeño Aeródromo Lado Aire Infraestructura Horizontal/vertical": (
        "LADO AIRE INFRAESTRUCTURA HORIZONTAL/VERTICAL"
    ),
    "Pequeño Aeródromo Lado Terrestre Infraestructura Horizontal/vertical": (
        "LADO TERRESTRE INFRAESTRUCTURA HORIZONTAL/VERTICAL"
    ),
    "Red Secundaria Lado Aire Infraestructura Horizontal": (
        "LADO AIRE INFRAESTRUCTURA HORIZONTAL"
    ),
}

_QUERY = """
SELECT
    codigo_bip,
    sector,
    subsector,
    nombre,
    "descripción" AS descripcion,
    justificación_proyecto AS justificacion_proyecto,
    descriptor_1,
    descriptor_2,
    descriptor_3,
    tipo_proyecto,
    año_eval_ex_post AS ano_eval
FROM ex_post
WHERE tipo_proyecto IS NOT NULL AND trim(tipo_proyecto) != ''
ORDER BY codigo_bip
"""


def normalize_bip(codigo: str) -> str:
    """EBI canónico sin dígito verificador (D-6)."""
    return codigo.strip().split("-")[0]


def canonical_tipo(raw: str) -> str:
    stripped = raw.strip()
    return TIPO_ALIASES.get(stripped, stripped)


def _str_field(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_expost_rows(db_path: Path) -> list[dict[str, object]]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rel = con.execute(_QUERY)
        columns = [d[0] for d in rel.description]
        return [dict(zip(columns, row, strict=False)) for row in rel.fetchall()]
    finally:
        con.close()


def build_casos(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    casos: list[dict[str, object]] = []
    for row in rows:
        codigo_raw = _str_field(row.get("codigo_bip"))
        if not codigo_raw:
            continue
        codigo = normalize_bip(codigo_raw)
        sector = _str_field(row.get("sector"))
        subsector = _str_field(row.get("subsector"))
        tipo = canonical_tipo(_str_field(row.get("tipo_proyecto")))
        ano = row.get("ano_eval")
        ano_tag = f"ano_eval:{int(ano)}" if ano is not None else "ano_eval:desconocido"
        casos.append(
            {
                "caso_id": f"expost-{codigo}",
                "input": {
                    "Codigo BIP": codigo,
                    "SECTOR": sector,
                    "SUBSECTOR": subsector,
                    "NOMBRE": _str_field(row.get("nombre")),
                    "descripción": _str_field(row.get("descripcion")),
                    "justificacion_proyecto": _str_field(row.get("justificacion_proyecto")),
                    "descriptor_1": _str_field(row.get("descriptor_1")),
                    "descriptor_2": _str_field(row.get("descriptor_2")),
                    "descriptor_3": _str_field(row.get("descriptor_3")),
                },
                "esperado": {"tipo_proyecto": tipo},
                "tags": ["expost", f"subsector:{subsector}", ano_tag],
            }
        )
    return casos


def write_golden_jsonl(
    casos: list[dict[str, object]],
    *,
    output_path: Path,
    version: str,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "nombre": "golden-tipo-proyecto",
        "version": version,
        "metrica_principal": "precision_l1_l2",
    }
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, ensure_ascii=False) + "\n")
        for caso in casos:
            fh.write(json.dumps(caso, ensure_ascii=False) + "\n")
    return len(casos)


def write_cobertura_subsector(
    casos: list[dict[str, object]],
    *,
    output_path: Path,
    total_subsectores: int = 84,
) -> None:
    counts: Counter[str] = Counter()
    for caso in casos:
        for tag in caso.get("tags", []):
            if isinstance(tag, str) and tag.startswith("subsector:"):
                counts[tag.removeprefix("subsector:")] += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["subsector", "casos_expost", "cubierto"],
        )
        writer.writeheader()
        for subsector, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            writer.writerow(
                {"subsector": subsector, "casos_expost": n, "cubierto": "si"}
            )
        writer.writerow(
            {
                "subsector": "_resumen",
                "casos_expost": sum(counts.values()),
                "cubierto": f"{len(counts)}/{total_subsectores}",
            }
        )


def convert_expost(
    db_path: Path,
    *,
    output_path: Path,
    version: str = "2.1.0-expost-holdout",
    cobertura_path: Path | None = None,
    holdout_ratio: float = 0.2,
    split_seed: int = 42,
    apply_split: bool = True,
) -> int:
    rows = load_expost_rows(db_path)
    casos = build_casos(rows)
    if apply_split:
        casos = assign_dev_holdout_tags(casos, holdout_ratio=holdout_ratio, seed=split_seed)
    n = write_golden_jsonl(casos, output_path=output_path, version=version)
    if cobertura_path is not None:
        write_cobertura_subsector(casos, output_path=cobertura_path)
    return n


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte informe_expost.duckdb → golden_tipo_proyecto.jsonl"
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_EXPOST_DB),
        help="DuckDB con tabla ex_post (gitignored en data/raw/)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_GOLDEN),
        help="JSONL de salida (formato sni_commons.eval)",
    )
    parser.add_argument(
        "--cobertura",
        default=str(EVAL_DIR / "golden_cobertura_subsector.csv"),
        help="CSV de cobertura por subsector (insumo UI)",
    )
    parser.add_argument("--version", default="2.1.0-expost-holdout", help="Versión del golden-set")
    parser.add_argument(
        "--holdout-ratio",
        type=float,
        default=0.2,
        help="Fracción holdout por subsector (default 0.2)",
    )
    parser.add_argument(
        "--split-seed",
        type=int,
        default=42,
        help="Semilla determinista del split dev/holdout",
    )
    parser.add_argument(
        "--no-split",
        action="store_true",
        help="No asignar tags dev/holdout (solo estrato expost)",
    )
    args = parser.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"ERROR: DuckDB no encontrado: {db}", file=sys.stderr)
        print(
            "Colocar informe_expost.duckdb en data/raw/ (no se commitea; D-11).",
            file=sys.stderr,
        )
        return 2

    n = convert_expost(
        db,
        output_path=Path(args.output),
        version=args.version,
        cobertura_path=Path(args.cobertura),
        holdout_ratio=args.holdout_ratio,
        split_seed=args.split_seed,
        apply_split=not args.no_split,
    )
    if n == 0:
        print("ERROR: ningún caso con tipo_proyecto en ex_post.", file=sys.stderr)
        return 1
    print(f"Golden generado: {args.output} ({n} casos, estrato expost)")
    if not args.no_split:
        casos = []
        with Path(args.output).open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                if "caso_id" in row:
                    casos.append(row)
        summary = split_summary(casos)
        print(
            f"Split dev/holdout: {summary['dev']} dev + {summary['holdout']} holdout "
            f"({summary['subsectores_dev']}/{summary['subsectores_holdout']} subsectores)"
        )
    print(f"Cobertura subsector: {args.cobertura}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
