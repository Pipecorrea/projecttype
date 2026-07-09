#!/usr/bin/env python3
"""Evalúa el golden-set tipo_proyecto con gate de CI (PT-10)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sni_commons.eval import cargar_golden, escribir_resultado

from projecttype.env import load_project_env
from projecttype.golden_eval import (
    confusion_matrix_csv,
    evaluar_golden_cascada,
    gate_golden,
    load_umbrales,
)
from projecttype.paths import DEFAULT_GOLDEN, DEFAULT_UMBRALES, EVAL_DIR


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Evalúa golden-set tipo_proyecto (PT-10).")
    parser.add_argument(
        "--golden",
        default=str(DEFAULT_GOLDEN),
        help="Ruta al golden-set YAML (formato sni_commons.eval)",
    )
    parser.add_argument(
        "--umbrales",
        default=str(DEFAULT_UMBRALES),
        help="Umbrales mínimos para gate CI",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Modo CI: L1+L2 reales, L3 MockLLM; exit 1 si gate falla",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Usa proveedor LLM configurado para L3 (corrida del dueño)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(EVAL_DIR),
        help="Directorio para JSON de ResultadoEval y CSV de confusión",
    )
    args = parser.parse_args()

    golden_path = Path(args.golden)
    if not golden_path.is_file():
        print(f"ERROR: golden no encontrado: {golden_path}", file=sys.stderr)
        print(
            "BLOQUEADOR: Submuestra_tp.xlsx ausente — regenerar con "
            "scripts/convert_submuestra_to_golden.py",
            file=sys.stderr,
        )
        return 2

    golden = cargar_golden(golden_path)
    enable_l3 = args.ci or args.real
    l3_mock = not args.real

    resultado, resultados = evaluar_golden_cascada(
        golden,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
    )

    out_dir = Path(args.output_dir)
    json_path = escribir_resultado(resultado, out_dir)
    conf_path = confusion_matrix_csv(
        resultados,
        golden,
        out_dir / f"confusion_{golden.version}.csv",
    )

    print("Métricas L1+L2:")
    for key, val in sorted(resultado.metricas.items()):
        print(f"  {key}: {val:.4f}")
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
