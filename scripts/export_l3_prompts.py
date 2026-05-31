#!/usr/bin/env python3
"""Exporta prompts L3 de muestra para revisión (sin llamar al LLM)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import polars as pl

from proyecttype.classifier_cascade import ClassifierCascade
from proyecttype.classifier_l3 import L3Config, ClassifierL3
from proyecttype.embeddings import L2Config
from proyecttype.paths import (
    DEFAULT_INPUT_CSV,
    DEFAULT_L3_PROMPTS,
    DEFAULT_OUTPUT_CASCADE_CSV,
    DEFAULT_TAXONOMY,
    OUTPUT_DIR,
)
from proyecttype.pipeline_cascade import classify_cascade_dataframe
from proyecttype.prompts import load_l3_prompt_config
from proyecttype.scorer import ScorerConfig


def _l3_candidates(df: pl.DataFrame) -> pl.DataFrame:
    residual = pl.col("estado_final").is_in(["ambiguo", "sin_match"])
    if "l3_estado" in df.columns:
        return df.filter(residual | pl.col("l3_estado").is_not_null())
    return df.filter(residual)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exporta prompts L3 para inspección (system + user JSON)."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_CSV),
        help="CSV BIP de entrada (si no hay resultados previos)",
    )
    parser.add_argument(
        "--resultados",
        default="",
        help="CSV con resultados L1+L2 (salta reclasificación)",
    )
    parser.add_argument("-t", "--taxonomy", default=str(DEFAULT_TAXONOMY))
    parser.add_argument("--prompts", default=str(DEFAULT_L3_PROMPTS))
    parser.add_argument("-n", "--sample", type=int, default=10, help="Número de prompts")
    parser.add_argument(
        "-o",
        "--output",
        default=str(OUTPUT_DIR / "l3_prompts_sample.jsonl"),
    )
    parser.add_argument(
        "--markdown",
        default=str(OUTPUT_DIR / "l3_prompts_sample.md"),
        help="Ejemplo legible del primer prompt",
    )
    args = parser.parse_args()

    cfg = load_l3_prompt_config(args.prompts)
    l3 = ClassifierL3.from_yaml(
        args.taxonomy,
        config=L3Config(prompts_path=Path(args.prompts), mock=True),
        mock=True,
    )

    if args.resultados:
        merged = pl.read_csv(args.resultados)
    else:
        cascade = ClassifierCascade.from_yaml(
            args.taxonomy,
            l1_config=ScorerConfig(),
            l2_config=L2Config(),
            enable_l3=False,
        )
        raw = pl.read_csv(args.input, infer_schema_length=1000, ignore_errors=True)
        merged = classify_cascade_dataframe(raw, cascade)

    candidates = _l3_candidates(merged).head(args.sample)
    if candidates.is_empty():
        print("No hay candidatos L3 (proyectos residuales L1+L2).")
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    for row in candidates.iter_rows(named=True):
        l2 = {
            "l2_tipo_id": row.get("l2_tipo_id"),
            "l2_tipo_nombre": row.get("l2_tipo_nombre"),
            "l2_estado": row.get("l2_estado"),
            "l2_similitud": row.get("l2_similitud"),
            "l2_margen": row.get("l2_margen"),
        }
        messages = l3.build_prompt_messages(
            sector=row.get("SECTOR") or row.get("sector_resuelto"),
            subsector=row.get("SUBSECTOR") or row.get("subsector_resuelto"),
            nombre=row.get("NOMBRE") or row.get("nombre"),
            descripcion=row.get("descripción") or row.get("descripcion"),
            justificacion=row.get("justificacion_proyecto") or row.get("justificacion"),
            descriptor_1=row.get("descriptor_1"),
            descriptor_2=row.get("descriptor_2"),
            descriptor_3=row.get("descriptor_3"),
            l1_tipo_id=row.get("l1_tipo_id"),
            l1_tipo_nombre=row.get("l1_tipo_nombre"),
            l1_estado=row.get("l1_estado"),
            l1_score=row.get("l1_score"),
            l1_margen=row.get("l1_margen"),
            l1_alternativas=row.get("l1_alternativas"),
            l2_tipo_id=l2["l2_tipo_id"],
            l2_tipo_nombre=l2["l2_tipo_nombre"],
            l2_estado=l2["l2_estado"],
            l2_similitud=l2["l2_similitud"],
            l2_margen=l2["l2_margen"],
            codigo_bip=str(row.get("Codigo BIP") or row.get("codigo_bip") or ""),
        )
        record = {
            "codigo_bip": row.get("Codigo BIP") or row.get("codigo_bip"),
            "sector": row.get("SECTOR") or row.get("sector_resuelto"),
            "subsector": row.get("SUBSECTOR") or row.get("subsector_resuelto"),
            "estado_final_previo": row.get("estado_final"),
            "prompts_yaml": str(args.prompts),
            "prompt_version": cfg.version,
            "edge_cases_count": len(cfg.edge_cases),
            "reasoning_steps_count": len(cfg.reasoning_steps),
            "system_chars": len(messages["system"]),
            "user_chars": len(messages["user"]),
            "system": messages["system"],
            "user": messages["user"],
        }
        user_data = json.loads(messages["user"])
        ctx = user_data.get("contexto_adicional") or {}
        record["few_shot_count"] = len(ctx.get("ejemplos_referencia") or [])
        record["confusion_pairs_count"] = len(ctx.get("pares_confusos") or [])
        record["composite_relations_count"] = len(ctx.get("relaciones_compuestas") or [])
        records.append(record)

    with output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    md_path = Path(args.markdown)
    first = records[0]
    md_path.write_text(
        "\n".join(
            [
                f"# Prompt L3 — {first['codigo_bip']}",
                "",
                f"- Sector: {first['sector']} / {first['subsector']}",
                f"- YAML v{first['prompt_version']}: `{first['prompts_yaml']}`",
                f"- Casos borde: {first['edge_cases_count']} | Pasos razonamiento: {first['reasoning_steps_count']}",
                f"- Few-shot: {first['few_shot_count']} | Pares confusos: {first['confusion_pairs_count']} | Compuestos: {first['composite_relations_count']}",
                f"- system: {first['system_chars']} chars | user: {first['user_chars']} chars",
                "",
                "## System",
                "",
                "```",
                first["system"],
                "```",
                "",
                "## User (JSON)",
                "",
                "```json",
                first["user"],
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Prompts exportados: {len(records)}")
    print(f"JSONL: {output}")
    print(f"Markdown (1er caso): {md_path}")
    print(f"\nConfig prompts: {args.prompts}")
    print(f"Casos borde definidos: {len(cfg.edge_cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
