"""Evaluación del golden-set tipo_proyecto (PT-10 / PT-23)."""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from sni_commons.eval import GoldenSet, ResultadoEval, Umbrales, gate
from sni_commons.eval.schemas import CasoGolden

from .classifier_cascade import ClassifierCascade
from .classifier_l3 import L3Config
from .embeddings import L2Config
from .evaluation import NivelMatch, clasificar_match, manual_en_tipos_l3, parse_l3_secundarios_row
from .inference_metadata import prompt_version
from .paths import DEFAULT_EMBEDDINGS_CACHE, DEFAULT_TAXONOMY
from .pipeline_cascade import classify_cascade_dataframe
from .scorer import ScorerConfig

ESTRATO_GATE_CI = "expost"


def filtrar_casos_por_estrato(golden: GoldenSet, estrato: str) -> list[CasoGolden]:
    """Casos del golden cuyo tag incluye el estrato (p. ej. ``expost``, ``dev``, ``holdout``)."""
    out: list[CasoGolden] = []
    for caso in golden.casos:
        if estrato in caso.tags:
            out.append(caso)
    return out


def subset_golden(golden: GoldenSet, estrato: str | None) -> GoldenSet:
    """Golden acotado a un estrato; ``None`` o ``all`` devuelve el set completo."""
    if estrato is None or estrato == "all":
        return golden
    casos = filtrar_casos_por_estrato(golden, estrato)
    return GoldenSet(
        nombre=golden.nombre,
        version=golden.version,
        metrica_principal=golden.metrica_principal,
        casos=casos,
    )


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


def _cascada_tipo(row: dict[str, Any]) -> tuple[str | None, str, str | None]:
    """Tipo final, estado y nivel de asignación (L1/L2/L3/residual)."""
    estado = str(row.get("estado_final") or "")
    tipo = row.get("tipo_final_nombre")
    nivel_raw = row.get("nivel_final")
    if estado == "asignado" and tipo:
        nivel = {1: "L1", 2: "L2", 3: "L3"}.get(int(nivel_raw) if nivel_raw is not None else -1)
        return str(tipo), estado, nivel
    return (str(tipo) if tipo else None), estado or "sin_match", "residual"


def _codigo_bip(caso: CasoGolden) -> str:
    return str(caso.input.get("Codigo BIP") or caso.input.get("codigo_bip") or caso.caso_id)


def _metricas_clasificacion(
    resultados: pl.DataFrame,
    casos: list[CasoGolden],
    *,
    tipo_fn: Callable[[dict[str, Any]], tuple[str | None, str]],
) -> dict[str, float]:
    by_bip = {
        str(r.get("Codigo BIP") or r.get("codigo_bip") or ""): r
        for r in resultados.to_dicts()
    }
    exactos = 0
    asignados = 0
    total = len(casos)

    for caso in casos:
        codigo = _codigo_bip(caso)
        row = by_bip.get(codigo)
        if row is None:
            continue
        manual = caso.esperado.get("tipo_proyecto")
        tipo, estado = tipo_fn(row)
        if estado == "asignado" and tipo:
            asignados += 1
            match = clasificar_match(tipo, str(manual), l1_estado="asignado")
            if match == NivelMatch.COINCIDENCIA_EXACTA:
                exactos += 1

    precision = exactos / asignados if asignados else 0.0
    cobertura = asignados / total if total else 0.0
    return {
        "precision": precision,
        "cobertura": cobertura,
        "exactos": float(exactos),
        "asignados": float(asignados),
        "total": float(total),
    }


def metricas_l1_l2(
    resultados: pl.DataFrame,
    golden: GoldenSet,
    *,
    estrato: str | None = ESTRATO_GATE_CI,
) -> dict[str, float]:
    """Precisión y cobertura agregadas L1+L2 sobre el golden (estrato opcional)."""
    casos = filtrar_casos_por_estrato(golden, estrato) if estrato else list(golden.casos)
    raw = _metricas_clasificacion(resultados, casos, tipo_fn=_l1_l2_tipo)
    return {
        "precision_l1_l2": raw["precision"],
        "cobertura_l1_l2": raw["cobertura"],
        "exactos_l1_l2": raw["exactos"],
        "asignados_l1_l2": raw["asignados"],
        "total": raw["total"],
    }


def metricas_cascada(
    resultados: pl.DataFrame,
    golden: GoldenSet,
    *,
    estrato: str | None = None,
) -> dict[str, float]:
    """Precisión y cobertura de la cascada completa L1→L2→L3."""
    casos = filtrar_casos_por_estrato(golden, estrato) if estrato else list(golden.casos)
    raw = _metricas_clasificacion(
        resultados,
        casos,
        tipo_fn=lambda row: _cascada_tipo(row)[:2],
    )
    return {
        "precision_cascada": raw["precision"],
        "cobertura_cascada": raw["cobertura"],
        "exactos_cascada": raw["exactos"],
        "asignados_cascada": raw["asignados"],
        "total_cascada": raw["total"],
    }


def _l3_puro_tipo(row: dict[str, Any]) -> tuple[str | None, str]:
    """Tipo y estado de L3 ignorando L1/L2 (eval forzada)."""
    estado = str(row.get("l3_estado") or "")
    tipo = row.get("l3_tipo_nombre")
    if estado == "asignado" and tipo:
        return str(tipo), estado
    return (str(tipo) if tipo else None), estado or "sin_match"


def metricas_l3_puro(
    resultados: pl.DataFrame,
    golden: GoldenSet,
    *,
    estrato: str | None = None,
    l3_force_limit: int,
) -> dict[str, float]:
    """Precisión L3 sobre N casos forzados, sin importar L1/L2."""
    casos = filtrar_casos_por_estrato(golden, estrato) if estrato else list(golden.casos)
    casos = casos[:l3_force_limit]
    by_bip = {
        str(r.get("Codigo BIP") or r.get("codigo_bip") or ""): r
        for r in resultados.to_dicts()
    }
    raw = _metricas_clasificacion(resultados, casos, tipo_fn=_l3_puro_tipo)
    ejecutados = 0
    multi_hit = 0
    for caso in casos:
        codigo = _codigo_bip(caso)
        row = by_bip.get(codigo)
        if row is None or row.get("l3_estado") is None:
            continue
        ejecutados += 1
        manual = caso.esperado.get("tipo_proyecto")
        principal = row.get("l3_tipo_nombre")
        estado = str(row.get("l3_estado") or "")
        tipo_principal: str | None
        if estado in ("asignado", "ambiguo") and principal:
            tipo_principal = str(principal)
        else:
            tipo_principal = str(principal) if principal else None
        secundarios = parse_l3_secundarios_row(row)
        if manual_en_tipos_l3(tipo_principal, secundarios, str(manual or "")):
            multi_hit += 1
    return {
        "precision_l3_puro": raw["precision"],
        "cobertura_l3_puro": raw["cobertura"],
        "exactos_l3_puro": raw["exactos"],
        "asignados_l3_puro": raw["asignados"],
        "ejecutados_l3_puro": float(ejecutados),
        "total_l3_puro": float(len(casos)),
        "multi_hit_l3_puro": multi_hit / ejecutados if ejecutados else 0.0,
        "exactos_multi_hit_l3_puro": float(multi_hit),
    }


def metricas_l3(
    resultados: pl.DataFrame,
    golden: GoldenSet,
    *,
    estrato: str | None = None,
) -> dict[str, float]:
    """Métricas solo sobre casos cuyo nivel final de asignación es L3."""
    casos = filtrar_casos_por_estrato(golden, estrato) if estrato else list(golden.casos)
    by_bip = {
        str(r.get("Codigo BIP") or r.get("codigo_bip") or ""): r
        for r in resultados.to_dicts()
    }
    exactos = 0
    asignados_l3 = 0
    residual_l1_l2 = 0
    total = len(casos)

    for caso in casos:
        codigo = _codigo_bip(caso)
        row = by_bip.get(codigo)
        if row is None:
            continue
        manual = caso.esperado.get("tipo_proyecto")
        _, estado_l12 = _l1_l2_tipo(row)
        if estado_l12 != "asignado":
            residual_l1_l2 += 1
        tipo, estado, nivel = _cascada_tipo(row)
        if nivel != "L3":
            continue
        if estado == "asignado" and tipo:
            asignados_l3 += 1
            match = clasificar_match(tipo, str(manual), l1_estado="asignado")
            if match == NivelMatch.COINCIDENCIA_EXACTA:
                exactos += 1

    precision = exactos / asignados_l3 if asignados_l3 else 0.0
    cobertura_residual = asignados_l3 / residual_l1_l2 if residual_l1_l2 else 0.0
    return {
        "precision_l3": precision,
        "cobertura_l3_residual": cobertura_residual,
        "exactos_l3": float(exactos),
        "asignados_l3": float(asignados_l3),
        "residual_l1_l2": float(residual_l1_l2),
        "total_l3": float(total),
    }


def run_cascade_on_golden(
    golden: GoldenSet,
    *,
    enable_l3: bool = False,
    l3_mock: bool = True,
    l3_limit: int | None = None,
    l3_force_limit: int | None = None,
    l3_concurrency: int | None = None,
    l3_config: L3Config | None = None,
    l3_cache_path: Path | None = None,
    l1_config: ScorerConfig | None = None,
    l2_config: L2Config | None = None,
    taxonomy_path: Path | None = None,
) -> pl.DataFrame:
    df = golden_to_dataframe(golden)
    tax = taxonomy_path or DEFAULT_TAXONOMY
    cascade = ClassifierCascade.from_yaml(
        tax,
        l1_config=l1_config,
        l2_config=l2_config,
        l3_config=l3_config,
        cache_dir=DEFAULT_EMBEDDINGS_CACHE,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
    )
    return classify_cascade_dataframe(
        df,
        cascade,
        l3_limit=l3_limit,
        l3_force_limit=l3_force_limit,
        l3_concurrency=l3_concurrency,
        l3_cache_path=l3_cache_path if enable_l3 and not l3_mock else None,
        l3_use_cache=l3_cache_path is not None,
    )


def evaluar_golden_cascada(
    golden: GoldenSet,
    *,
    enable_l3: bool = False,
    l3_mock: bool = True,
    l3_limit: int | None = None,
    l3_force_limit: int | None = None,
    l3_concurrency: int | None = None,
    l3_config: L3Config | None = None,
    l3_cache_path: Path | None = None,
    l1_config: ScorerConfig | None = None,
    l2_config: L2Config | None = None,
    taxonomy_path: Path | None = None,
    estrato_gate: str | None = ESTRATO_GATE_CI,
    estrato_eval: str | None = None,
    incluir_metricas_cascada: bool = False,
) -> tuple[ResultadoEval, pl.DataFrame]:
    eval_golden = subset_golden(golden, estrato_eval)
    resultados = run_cascade_on_golden(
        eval_golden,
        enable_l3=enable_l3,
        l3_mock=l3_mock,
        l3_limit=l3_limit,
        l3_force_limit=l3_force_limit,
        l3_concurrency=l3_concurrency,
        l3_config=l3_config,
        l3_cache_path=l3_cache_path,
        l1_config=l1_config,
        l2_config=l2_config,
        taxonomy_path=taxonomy_path,
    )
    estrato_metricas = estrato_eval or estrato_gate
    metricas = metricas_l1_l2(resultados, golden, estrato=estrato_metricas)
    if incluir_metricas_cascada:
        metricas.update(metricas_cascada(resultados, golden, estrato=estrato_metricas))
        metricas.update(metricas_l3(resultados, golden, estrato=estrato_metricas))
    if l3_force_limit is not None:
        metricas.update(
            metricas_l3_puro(
                resultados,
                golden,
                estrato=estrato_metricas,
                l3_force_limit=l3_force_limit,
            )
        )
    casos_gate = (
        filtrar_casos_por_estrato(golden, estrato_gate)
        if estrato_gate
        else list(golden.casos)
    )
    casos_eval = (
        filtrar_casos_por_estrato(golden, estrato_metricas)
        if estrato_metricas
        else list(golden.casos)
    )
    modelo = "mock-llm" if l3_mock else (l3_config.llm.resolved_model() if l3_config and l3_config.llm else "real-llm")
    resultado = ResultadoEval(
        golden_version=golden.version,
        modelo=modelo,
        prompt_version=prompt_version(),
        timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
        metricas={
            **metricas,
            "casos_estrato": float(len(casos_gate)),
            "casos_evaluados": float(len(casos_eval)),
        },
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
    *,
    estrato: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_bip = {str(r.get("Codigo BIP") or ""): r for r in resultados.to_dicts()}
    rows_out: list[dict[str, str]] = []
    pairs: Counter[tuple[str, str]] = Counter()
    casos = filtrar_casos_por_estrato(golden, estrato) if estrato else list(golden.casos)

    for caso in casos:
        codigo = _codigo_bip(caso)
        row = by_bip.get(codigo, {})
        manual = str(caso.esperado.get("tipo_proyecto") or "")
        pred_l12, _ = _l1_l2_tipo(row)
        pred_cascada, _, nivel = _cascada_tipo(row)
        match = clasificar_match(
            pred_cascada,
            manual,
            l1_estado="asignado" if pred_cascada else "sin_match",
        )
        split = next((t for t in caso.tags if t in ("dev", "holdout")), "")
        rows_out.append(
            {
                "caso_id": caso.caso_id,
                "codigo_bip": codigo,
                "split": split,
                "tipo_manual": manual,
                "tipo_predicho_l1_l2": str(pred_l12 or ""),
                "tipo_predicho_cascada": str(pred_cascada or ""),
                "match_nivel": match.value,
                "nivel_asignacion": str(nivel or ""),
                "l1_estado": str(row.get("l1_estado") or ""),
                "l2_estado": str(row.get("l2_estado") or ""),
                "l3_estado": str(row.get("l3_estado") or ""),
                "nivel_final": str(row.get("nivel_final") or ""),
            }
        )
        if match == NivelMatch.DISCREPANCIA:
            pairs[(manual, str(pred_cascada or ""))] += 1

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "caso_id",
                "codigo_bip",
                "split",
                "tipo_manual",
                "tipo_predicho_l1_l2",
                "tipo_predicho_cascada",
                "match_nivel",
                "nivel_asignacion",
                "l1_estado",
                "l2_estado",
                "l3_estado",
                "nivel_final",
            ],
        )
        writer.writeheader()
        writer.writerows(rows_out)

    summary_path = path.with_name(path.stem + "_pairs.csv")
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        pair_writer = csv.writer(fh)
        pair_writer.writerow(["tipo_manual", "tipo_predicho_cascada", "count"])
        for (manual, pred), count in sorted(pairs.items()):
            pair_writer.writerow([manual, pred, count])

    return path
