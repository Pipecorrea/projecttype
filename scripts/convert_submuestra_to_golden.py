#!/usr/bin/env python3
"""Convierte Submuestra_tp.xlsx al golden-set sni_commons.eval (PT-10)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from projecttype.evaluation import load_submuestra
from projecttype.paths import DEFAULT_GOLDEN, DEFAULT_SUBMUESTRA


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {c.strip(): c for c in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def convert_submuestra(
    submuestra_path: Path,
    *,
    output_path: Path,
    version: str = "1.0.0",
) -> int:
    df = load_submuestra(submuestra_path)
    cols = [c.strip() for c in df.columns]

    codigo_col = _pick_column(cols, ("codigo_bip", "Codigo BIP", "Código BIP")) or "codigo_bip"
    sector_col = _pick_column(cols, ("sector", "SECTOR")) or "sector"
    subsector_col = _pick_column(cols, ("subsector", "SUBSECTOR")) or "subsector"
    nombre_col = _pick_column(cols, ("nombre", "NOMBRE")) or "nombre"
    just_col = _pick_column(cols, ("justificacion_proyecto", "justificación_proyecto"))
    desc_col = _pick_column(cols, ("descripción", "descripcion"))
    d1 = _pick_column(cols, ("descriptor_1",))
    d2 = _pick_column(cols, ("descriptor_2",))
    d3 = _pick_column(cols, ("descriptor_3",))

    casos = []
    for idx, row in enumerate(df.iter_rows(named=True)):
        manual = row.get("tipo_proyecto")
        if manual is None or str(manual).strip() == "":
            continue
        caso_input = {
            "Codigo BIP": str(row.get(codigo_col) or f"SUB-{idx}"),
            "SECTOR": str(row.get(sector_col) or ""),
            "SUBSECTOR": str(row.get(subsector_col) or ""),
            "NOMBRE": str(row.get(nombre_col) or ""),
            "descripción": str(row.get(desc_col) or "") if desc_col else "",
            "justificacion_proyecto": str(row.get(just_col) or "") if just_col else "",
            "descriptor_1": str(row.get(d1) or "") if d1 else "",
            "descriptor_2": str(row.get(d2) or "") if d2 else "",
            "descriptor_3": str(row.get(d3) or "") if d3 else "",
        }
        casos.append(
            {
                "caso_id": f"sub-{idx:04d}",
                "input": caso_input,
                "esperado": {"tipo_proyecto": str(manual).strip()},
                "tags": ["submuestra"],
            }
        )

    golden = {
        "nombre": "golden-tipo-proyecto",
        "version": version,
        "metrica_principal": "precision_l1_l2",
        "casos": casos,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(golden, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Golden generado: {output_path} ({len(casos)} casos)")
    return len(casos)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte Submuestra_tp.xlsx → golden_tipo_proyecto.yaml"
    )
    parser.add_argument(
        "--submuestra",
        default=str(DEFAULT_SUBMUESTRA),
        help="Excel con etiquetado manual (col tipo_proyecto)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_GOLDEN),
        help="YAML de salida (formato sni_commons.eval)",
    )
    parser.add_argument("--version", default="1.0.0", help="Versión del golden-set")
    args = parser.parse_args()

    src = Path(args.submuestra)
    if not src.is_file():
        print(f"ERROR: Submuestra no encontrada: {src}", file=sys.stderr)
        print(
            "Colocar Submuestra_tp.xlsx en data/raw/ y re-ejecutar, "
            "o usar el fixture data/golden/golden_tipo_proyecto.yaml.",
            file=sys.stderr,
        )
        return 2

    n = convert_submuestra(src, output_path=Path(args.output), version=args.version)
    if n == 0:
        print("ERROR: ningún caso con tipo_proyecto en la submuestra.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
