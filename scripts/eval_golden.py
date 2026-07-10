#!/usr/bin/env python3
"""Evalúa el golden-set tipo_proyecto con gate de CI (PT-10 / PT-23)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sni_commons.eval import cargar_golden, escribir_resultado

from projecttype.classifier_l3 import L3Config
from projecttype.env import load_project_env
from projecttype.golden_eval import (
    ESTRATO_GATE_CI,
    confusion_matrix_csv,
    evaluar_golden_cascada,
    gate_golden,
    load_umbrales,
    subset_golden,
)
from projecttype.golden_split import split_summary
from projecttype.llm.provider import (
    check_provider_available,
    default_l3_concurrency,
    default_llm_provider,
    describe_provider,
)
from projecttype.llm_client import LLMConfig
from projecttype.paths import DEFAULT_GOLDEN, DEFAULT_L3_CACHE_JSONL, DEFAULT_UMBRALES, EVAL_DIR

PILOT_L3_LIMIT = 30


def _print_metricas(resultado, *, secciones: list[str]) -> None:
    metricas = resultado.metricas
    grupos = {
        "L1+L2": ("precision_l1_l2", "cobertura_l1_l2", "exactos_l1_l2", "asignados_l1_l2"),
        "Cascada": (
            "precision_cascada",
            "cobertura_cascada",
            "exactos_cascada",
            "asignados_cascada",
        ),
        "L3": (
            "precision_l3",
            "cobertura_l3_residual",
            "exactos_l3",
            "asignados_l3",
            "residual_l1_l2",
        ),
        "L3 puro": (
            "precision_l3_puro",
            "cobertura_l3_puro",
            "exactos_l3_puro",
            "asignados_l3_puro",
            "ejecutados_l3_puro",
            "total_l3_puro",
            "multi_hit_l3_puro",
            "exactos_multi_hit_l3_puro",
        ),
        "Contexto": ("total", "total_cascada", "total_l3", "casos_evaluados", "casos_estrato"),
    }
    for nombre in secciones:
        keys = grupos.get(nombre, ())
        present = [k for k in keys if k in metricas]
        if not present:
            continue
        print(f"Métricas {nombre}:")
        for key in present:
            val = metricas[key]
            print(f"  {key}: {val:.4f}" if isinstance(val, float) else f"  {key}: {val}")


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Evalúa golden-set tipo_proyecto (PT-10/PT-23).")
    parser.add_argument(
        "--golden",
        default=str(DEFAULT_GOLDEN),
        help="Ruta al golden-set YAML/JSONL (formato sni_commons.eval)",
    )
    parser.add_argument(
        "--umbrales",
        default=str(DEFAULT_UMBRALES),
        help="Umbrales mínimos para gate CI (solo L1+L2)",
    )
    parser.add_argument(
        "--estrato",
        default=None,
        choices=["expost", "dev", "holdout", "all"],
        help="Subconjunto a evaluar (default: expost en --ci, all fuera de CI)",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Modo CI: L1+L2 reales, L3 MockLLM; gate solo L1+L2 estrato expost",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Usa proveedor LLM configurado para L3 (corrida del dueño)",
    )
    parser.add_argument(
        "--l3-limit",
        type=int,
        default=None,
        help=f"Máximo de llamadas LLM L3 (default piloto: {PILOT_L3_LIMIT} con --real)",
    )
    parser.add_argument(
        "--full-l3",
        action="store_true",
        help="Evaluar todo el residual L3 del estrato (sin tope de piloto)",
    )
    parser.add_argument(
        "--l3-pure",
        type=int,
        default=None,
        metavar="N",
        help="Forzar L3 sobre los primeros N casos del estrato (accuracy puro L3, requiere --real)",
    )
    parser.add_argument(
        "--l3-provider",
        choices=["gemini", "gemini-studio", "google", "vertex", "anthropic", "openai", "ollama"],
        default=None,
        help=f"Proveedor L3 (default: LLM_PROVIDER o {default_llm_provider()!r} → Vertex en gemini)",
    )
    parser.add_argument(
        "--l3-model",
        default=None,
        help="Modelo L3 (default según proveedor)",
    )
    parser.add_argument(
        "--l3-concurrency",
        type=int,
        default=None,
        help=f"Hilos paralelos L3 (default: LLM_MAX_CONCURRENCY o {default_l3_concurrency()})",
    )
    parser.add_argument(
        "--no-l3-cache",
        action="store_true",
        help="No leer/escribir caché L3 JSONL",
    )
    parser.add_argument(
        "--output-dir",
        default=str(EVAL_DIR),
        help="Directorio para JSON de ResultadoEval y CSV de confusión",
    )
    args = parser.parse_args()

    if args.l3_pure is not None and not args.real:
        print("ERROR: --l3-pure requiere --real (LLM real).", file=sys.stderr)
        return 2
    if args.l3_pure is not None and args.l3_pure < 1:
        print("ERROR: --l3-pure debe ser >= 1.", file=sys.stderr)
        return 2

    golden_path = Path(args.golden)
    if not golden_path.is_file():
        print(f"ERROR: golden no encontrado: {golden_path}", file=sys.stderr)
        print(
            "Regenerar con: uv run python scripts/convert_expost_to_golden.py "
            "(requiere data/raw/informe_expost.duckdb, gitignored).",
            file=sys.stderr,
        )
        return 2

    golden = cargar_golden(golden_path)
    estrato_eval = args.estrato or ("dev" if args.l3_pure else None) or (ESTRATO_GATE_CI if args.ci else "all")
    if estrato_eval == "all":
        estrato_eval = None
    estrato_gate = ESTRATO_GATE_CI if args.ci else estrato_eval

    if args.ci and args.estrato not in (None, ESTRATO_GATE_CI):
        print(
            "ERROR: --ci solo gatea L1+L2 sobre estrato expost; "
            "usa --estrato expost o quita --ci.",
            file=sys.stderr,
        )
        return 2

    tagged = [c for c in golden.casos if "dev" in c.tags or "holdout" in c.tags]
    if tagged:
        summary = split_summary(
            [
                {
                    "caso_id": c.caso_id,
                    "tags": c.tags,
                }
                for c in golden.casos
            ]
        )
        print(
            f"Golden split: {summary['dev']} dev + {summary['holdout']} holdout "
            f"({summary['subsectores_dev']}/{summary['subsectores_holdout']} subsectores)"
        )
    elif estrato_eval in ("dev", "holdout"):
        print(
            "ERROR: golden sin tags dev/holdout; regenerar con convert_expost_to_golden.py",
            file=sys.stderr,
        )
        return 2

    enable_l3 = args.ci or args.real or estrato_eval in ("dev", "holdout") or args.l3_pure is not None
    l3_mock = not args.real
    incluir_cascada = enable_l3 and (args.real or estrato_eval in ("dev", "holdout") or args.l3_pure is not None)

    l3_provider = args.l3_provider or default_llm_provider()
    l3_limit = args.l3_limit
    l3_force_limit = args.l3_pure
    l3_concurrency = args.l3_concurrency
    if args.real and l3_limit is None and not args.full_l3 and l3_force_limit is None:
        l3_limit = PILOT_L3_LIMIT
        print(f"Piloto L3: máximo {l3_limit} llamadas (--full-l3 para evaluar todo el residual)")
    if l3_force_limit is not None:
        print(
            f"Eval L3 puro: forzar L3 en los primeros {l3_force_limit} casos del estrato "
            f"(sin filtrar por residual L1/L2)"
        )
    if l3_concurrency is None and args.real:
        l3_concurrency = 1 if l3_force_limit else default_l3_concurrency()

    l3_config: L3Config | None = None
    if enable_l3 and not l3_mock:
        check_provider_available(l3_provider)
        llm_config = LLMConfig(provider=l3_provider, model=args.l3_model or "")  # type: ignore[arg-type]
        print(f"L3 backend: {describe_provider(l3_provider)}")
        if l3_concurrency and l3_concurrency > 1:
            print(f"  Concurrencia: {l3_concurrency} hilos en paralelo")
        interval = llm_config.effective_request_interval()
        if interval > 0:
            print(f"  Throttle: {interval:g}s entre llamadas (~{60 / interval:.0f} req/min)")
        l3_config = L3Config(llm=llm_config, mock=False)

    resultado, resultados = evaluar_golden_cascada(
        golden,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
        l3_limit=l3_limit,
        l3_force_limit=l3_force_limit,
        l3_concurrency=l3_concurrency,
        l3_config=l3_config,
        l3_cache_path=None if args.no_l3_cache else DEFAULT_L3_CACHE_JSONL,
        estrato_gate=estrato_gate,
        estrato_eval=estrato_eval,
        incluir_metricas_cascada=incluir_cascada,
    )

    out_dir = Path(args.output_dir)
    suffix = estrato_eval or "all"
    if l3_force_limit is not None:
        suffix = f"{suffix}_l3pure{l3_force_limit}"
    json_path = escribir_resultado(resultado, out_dir)
    conf_path = confusion_matrix_csv(
        resultados,
        subset_golden(golden, estrato_eval),
        out_dir / f"confusion_{golden.version}_{suffix}.csv",
        estrato=estrato_eval,
    )

    secciones = ["L1+L2"]
    if incluir_cascada:
        secciones.extend(["Cascada", "L3"])
    if l3_force_limit is not None:
        secciones.append("L3 puro")
    secciones.append("Contexto")
    _print_metricas(resultado, secciones=secciones)
    print(f"prompt_version: {resultado.prompt_version}")
    print(f"modelo: {resultado.modelo}")
    print(f"ResultadoEval: {json_path}")
    print(f"Matriz confusión: {conf_path}")

    if args.ci:
        umbrales = load_umbrales(Path(args.umbrales))
        ok, mensaje = gate_golden(resultado, umbrales)
        print(mensaje)
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
