"""Evaluación del golden-set tipo_proyecto (PT-10)."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from sni_commons.eval import GoldenSet, ResultadoEval, Umbrales, gate

from .classifier_cascade import ClassifierCascade
from .evaluation import NivelMatch, clasificar_match
from .inference_metadata import prompt_version
from .paths import DEFAULT_EMBEDDINGS_CACHE, DEFAULT_TAXONOMY
from .pipeline_cascade import classify_cascade_dataframe
from .scorer import ScorerConfig


@dataclass(frozen=True)
class UmbralesGolden:
    precision_l1_l2: float
    cobertura_l1_l2: float


def load_umbrales(path: Path) -> UmbralesGolden:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("umbrales") or []
    by_metric = {str(item["metrica"]): float(item["minimo"]) for item in entries}
    return UmbralesGolden(
        precision_l1_l2=by_metric["precision_l1_l2"],
        cobertura_l1_l2=by_metric["cobertura_l1_l2"],
    )


def golden_to_dataframe(golden: GoldenSet) -> pl.DataFrame:
    rows = [dict(caso.input) for caso in golden.casos]
    return pl.DataFrame(rows)


def _l1_l2_tipo(row: dict[str, Any]) -> tuple[str | None, str]:
    """Tipo y estado efectivos tras L1+L2 (sin L3)."""
    if row.get("l1_estado") == "asignado":
        return row.get("l1_tipo_nombre"), "asignado"
    if row.get("l2_estado") == "asignado":
        return row.get("l2_tipo_nombre"), "asignado"
    return row.get("l1_tipo_nombre"), str(row.get("l1_estado") or "sin_match")


def metricas_l1_l2(resultados: pl.DataFrame, golden: GoldenSet) -> dict[str, float]:
    """Precisión y cobertura agregadas L1+L2 sobre el golden."""
    by_bip = {str(r.get("Codigo BIP") or r.get("codigo_bip") or ""): r for r in resultados.to_dicts()}
    exactos = 0
    asignados = 0
    total = len(golden.casos)

    for caso in golden.casos:
        codigo = str(caso.input.get("Codigo BIP") or caso.input.get("codigo_bip") or caso.caso_id)
        row = by_bip.get(codigo)
        if row is None:
            continue
        manual = caso.esperado.get("tipo_proyecto")
        tipo, estado = _l1_l2_tipo(row)
        if estado == "asignado" and tipo:
            asignados += 1
            match = clasificar_match(tipo, str(manual), l1_estado="asignado")
            if match == NivelMatch.COINCIDENCIA_EXACTA:
                exactos += 1

    precision = exactos / asignados if asignados else 0.0
    cobertura = asignados / total if total else 0.0
    return {
        "precision_l1_l2": precision,
        "cobertura_l1_l2": cobertura,
        "exactos_l1_l2": float(exactos),
        "asignados_l1_l2": float(asignados),
        "total": float(total),
    }


def run_cascade_on_golden(
    golden: GoldenSet,
    *,
    enable_l3: bool = False,
    l3_mock: bool = True,
    l1_config: ScorerConfig | None = None,
    taxonomy_path: Path | None = None,
) -> pl.DataFrame:
    df = golden_to_dataframe(golden)
    tax = taxonomy_path or DEFAULT_TAXONOMY
    cascade = ClassifierCascade.from_yaml(
        tax,
        l1_config=l1_config,
        cache_dir=DEFAULT_EMBEDDINGS_CACHE,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
    )
    l3_model = "mock-llm"
    if enable_l3 and cascade.l3 and cascade.l3.config.llm:
        l3_model = cascade.l3.config.llm.resolved_model()
    return classify_cascade_dataframe(
        df,
        cascade,
        l3_model=l3_model,
    )


def evaluar_golden_cascada(
    golden: GoldenSet,
    *,
    enable_l3: bool = False,
    l3_mock: bool = True,
    l1_config: ScorerConfig | None = None,
    taxonomy_path: Path | None = None,
) -> tuple[ResultadoEval, pl.DataFrame]:
    resultados = run_cascade_on_golden(
        golden,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
        l1_config=l1_config,
        taxonomy_path=taxonomy_path,
    )
    metricas = metricas_l1_l2(resultados, golden)
    modelo = "mock-llm" if l3_mock else "real-llm"
    resultado = ResultadoEval(
        golden_version=golden.version,
        modelo=modelo,
        prompt_version=prompt_version(),
        timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
        metricas=metricas,
        por_caso=[],
    )
    return resultado, resultados


def gate_golden(resultado: ResultadoEval, umbrales: UmbralesGolden) -> tuple[bool, str]:
    return gate(
        resultado,
        [
            Umbrales(metrica="precision_l1_l2", minimo=umbrales.precision_l1_l2),
            Umbrales(metrica="cobertura_l1_l2", minimo=umbrales.cobertura_l1_l2),
        ],
    )


def confusion_matrix_csv(
    resultados: pl.DataFrame,
    golden: GoldenSet,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_bip = {str(r.get("Codigo BIP") or ""): r for r in resultados.to_dicts()}
    rows_out: list[dict[str, str]] = []
    pairs: Counter[tuple[str, str]] = Counter()

    for caso in golden.casos:
        codigo = str(caso.input.get("Codigo BIP") or caso.caso_id)
        row = by_bip.get(codigo, {})
        manual = str(caso.esperado.get("tipo_proyecto") or "")
        pred, _ = _l1_l2_tipo(row)
        pred = str(pred or "")
        pairs[(manual, pred)] += 1
        rows_out.append(
            {
                "caso_id": caso.caso_id,
                "codigo_bip": codigo,
                "tipo_manual": manual,
                "tipo_predicho_l1_l2": pred,
                "l1_estado": str(row.get("l1_estado") or ""),
                "l2_estado": str(row.get("l2_estado") or ""),
                "nivel_final": str(row.get("nivel_final") or ""),
            }
        )

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "caso_id",
                "codigo_bip",
                "tipo_manual",
                "tipo_predicho_l1_l2",
                "l1_estado",
                "l2_estado",
                "nivel_final",
            ],
        )
        writer.writeheader()
        writer.writerows(rows_out)

    summary_path = path.with_name(path.stem + "_pairs.csv")
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        pair_writer = csv.writer(fh)
        pair_writer.writerow(["tipo_manual", "tipo_predicho", "count"])
        for (manual, pred), count in sorted(pairs.items()):
            pair_writer.writerow([manual, pred, count])

    return path
