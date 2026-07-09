#!/usr/bin/env python3
"""CLI cascada L1 → L2 → L3 (keywords + embeddings + LLM)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from collections import Counter
from pathlib import Path

import polars as pl

from projecttype.classifier_l3 import L3Config
from projecttype.embeddings import L2Config
from projecttype.env import load_project_env
from projecttype.llm_client import (
    LLMConfig,
    check_gemini_available,
    check_ollama_available,
    list_ollama_models,
)
from projecttype.paths import (
    DEFAULT_EMBEDDINGS_CACHE,
    DEFAULT_INPUT_CSV,
    DEFAULT_L3_CACHE_JSONL,
    DEFAULT_L3_PROGRESS_JSONL,
    DEFAULT_OUTPUT_CASCADE_CSV,
    DEFAULT_OUTPUT_CASCADE_L3_CSV,
    DEFAULT_TAXONOMY,
)
from projecttype.pipeline_cascade import classify_cascade_csv
from projecttype.scorer import ScorerConfig

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_L2 = L2Config()
_DEFAULT_L3 = L3Config()
_DEFAULT_LLM = LLMConfig()


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Clasificador cascada L1 + L2 + L3.")
    parser.add_argument("-i", "--input", default=str(DEFAULT_INPUT_CSV))
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-t", "--taxonomy", default=str(DEFAULT_TAXONOMY))
    parser.add_argument("--cache-dir", default=str(DEFAULT_EMBEDDINGS_CACHE))
    parser.add_argument("--min-similarity", type=float, default=_DEFAULT_L2.min_similarity)
    parser.add_argument("--min-margin-l2", type=float, default=_DEFAULT_L2.min_margin)
    parser.add_argument("--enable-l3", action="store_true", help="Activa Nivel 3 (LLM)")
    parser.add_argument("--l3-mock", action="store_true", help="L3 sin API (cliente mock)")
    parser.add_argument(
        "--l3-provider",
        choices=("ollama", "openai", "google"),
        default=_DEFAULT_LLM.provider,
        help="Backend LLM para L3 (default: ollama; google = Gemini AI Studio)",
    )
    parser.add_argument(
        "--l3-model",
        default="",
        help="Modelo LLM (Ollama: llama3.2; Google: gemini-2.0-flash; OpenAI: gpt-4o-mini)",
    )
    parser.add_argument(
        "--ollama-url",
        default=_DEFAULT_LLM.ollama_base_url,
        help="URL base de Ollama (default: http://localhost:11434)",
    )
    parser.add_argument("--l3-min-confidence", type=float, default=_DEFAULT_L3.min_confidence)
    parser.add_argument(
        "--l3-limit",
        type=int,
        default=None,
        help="Máximo de proyectos L3 nuevos por corrida (omite los ya en caché)",
    )
    parser.add_argument(
        "--l3-progress-interval",
        type=int,
        default=1,
        help="Mostrar avance L3 en consola cada N proyectos (el archivo de progreso registra cada uno)",
    )
    parser.add_argument(
        "--l3-progress-file",
        default=str(DEFAULT_L3_PROGRESS_JSONL),
        help="Archivo JSONL con avance L3 (tail -f para monitorear)",
    )
    parser.add_argument(
        "--l3-cache-file",
        default=str(DEFAULT_L3_CACHE_JSONL),
        help="Caché JSONL de resultados L3 por código BIP",
    )
    parser.add_argument(
        "--l3-no-cache",
        action="store_true",
        help="Ignorar caché L3 (reclasificar todo)",
    )
    parser.add_argument(
        "--l3-prompts",
        default=str(ROOT / "data" / "prompts" / "l3.yaml"),
        help="YAML con system prompt y casos borde",
    )
    parser.add_argument(
        "--list-ollama-models",
        action="store_true",
        help="Lista modelos Ollama instalados y sale",
    )
    parser.add_argument("--no-excel", action="store_true")
    args = parser.parse_args()

    if args.list_ollama_models:
        try:
            models = list_ollama_models(base_url=args.ollama_url)
        except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError) as exc:
            print(f"Error: no se pudo conectar a Ollama en {args.ollama_url}: {exc}", file=sys.stderr)
            return 1
        if not models:
            print("No hay modelos instalados. Ejemplo: ollama pull llama3.2")
            return 1
        print("Modelos Ollama disponibles:")
        for name in models:
            print(f"  {name}")
        return 0

    output = args.output
    if output is None:
        output = str(DEFAULT_OUTPUT_CASCADE_L3_CSV if args.enable_l3 else DEFAULT_OUTPUT_CASCADE_CSV)

    llm_config = LLMConfig(
        provider=args.l3_provider,
        model=args.l3_model,
        ollama_base_url=args.ollama_url,
    )
    l2_config = L2Config(
        min_similarity=args.min_similarity,
        min_margin=args.min_margin_l2,
    )
    l3_config = L3Config(
        min_confidence=args.l3_min_confidence,
        llm=llm_config,
        mock=args.l3_mock,
        prompts_path=Path(args.l3_prompts),
    )

    if args.enable_l3 and not args.l3_mock:
        if args.l3_provider == "openai":
            import os

            if not os.environ.get("OPENAI_API_KEY"):
                print(
                    "Error: --l3-provider openai requiere OPENAI_API_KEY o usar --l3-mock.",
                    file=sys.stderr,
                )
                return 1
            print(f"L3 OpenAI: modelo: {llm_config.resolved_model()}")
        elif args.l3_provider == "google":
            try:
                check_gemini_available()
            except RuntimeError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                print(
                    "  Define GEMINI_API_KEY en .env (copia .env.example) o exporta la variable.",
                    file=sys.stderr,
                )
                return 1
            print(f"L3 Gemini (AI Studio): modelo: {llm_config.resolved_model()}")
            interval = llm_config.effective_request_interval()
            if interval > 0:
                rpm = 60 / interval
                print(f"  Rate limit: {interval:g}s entre llamadas (~{rpm:.0f} req/min, cuota free)")
        else:
            try:
                check_ollama_available(
                    base_url=args.ollama_url,
                    model=llm_config.resolved_model(),
                )
            except RuntimeError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            print(f"L3 Ollama: {args.ollama_url} | modelo: {llm_config.resolved_model()}")

    l3_progress_file = Path(args.l3_progress_file) if args.enable_l3 else None
    if l3_progress_file is not None:
        l3_progress_file.parent.mkdir(parents=True, exist_ok=True)
        l3_progress_file.write_text("", encoding="utf-8")
        print(f"Avance L3 → {l3_progress_file}")
        print(f"  Monitorear: tail -f {l3_progress_file}")
        print("  Resumen:    python scripts/l3_status.py")

    result, csv_path, excel_path = classify_cascade_csv(
        args.input,
        output,
        args.taxonomy,
        l1_config=ScorerConfig(),
        l2_config=l2_config,
        l3_config=l3_config,
        cache_dir=Path(args.cache_dir),
        enable_l3=args.enable_l3,
        l3_mock=args.l3_mock,
        l3_limit=args.l3_limit,
        l3_progress_interval=args.l3_progress_interval,
        l3_progress_file=l3_progress_file,
        l3_cache_path=Path(args.l3_cache_file) if args.enable_l3 else None,
        l3_use_cache=not args.l3_no_cache,
        write_excel=not args.no_excel,
    )

    total = result.height
    print(f"Proyectos procesados: {total}")
    print("\nL1:")
    for estado, count in Counter(result["l1_estado"].to_list()).most_common():
        print(f"  {estado:15s} {count:5d}  ({100*count/total:.1f}%)")

    l2_ran = result.filter(pl.col("l2_estado").is_not_null()).height
    print(f"\nL2 ejecutado en: {l2_ran} proyectos (residual L1)")
    if l2_ran:
        l2_subset = result.filter(pl.col("l2_estado").is_not_null())
        for estado, count in Counter(l2_subset["l2_estado"].to_list()).most_common():
            print(f"  {estado:15s} {count:5d}  ({100*count/l2_ran:.1f}%)")

    if args.enable_l3:
        l3_ran = result.filter(pl.col("l3_estado").is_not_null()).height
        limit_note = f" (límite {args.l3_limit})" if args.l3_limit else ""
        print(f"\nL3 ejecutado en: {l3_ran} proyectos (residual L1+L2){limit_note}")
        if l3_ran:
            l3_subset = result.filter(pl.col("l3_estado").is_not_null())
            for estado, count in Counter(l3_subset["l3_estado"].to_list()).most_common():
                print(f"  {estado:15s} {count:5d}  ({100*count/l3_ran:.1f}%)")

    print("\nFinal (cascada):")
    for estado, count in Counter(result["estado_final"].to_list()).most_common():
        print(f"  {estado:15s} {count:5d}  ({100*count/total:.1f}%)")

    by_nivel = Counter(result["nivel_final"].to_list())
    print("\nNivel final:")
    for nivel, count in sorted(by_nivel.items()):
        print(f"  nivel {nivel}: {count}")

    print(f"\nGuardado en: {csv_path}")
    if excel_path:
        print(f"Excel: {excel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
