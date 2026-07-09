"""Contexto dinámico para prompts L3 (pares confusos, compuestos, few-shot)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .aliases import resolve_sector_subsector
from .paths import PROJECT_ROOT, TAXONOMY_DIR
from .text_utils import normalize_key

PROMPTS_DIR = PROJECT_ROOT / "data" / "prompts"
DEFAULT_FEW_SHOT = PROMPTS_DIR / "few_shot_examples.yaml"
DEFAULT_FEW_SHOT_MINED = PROMPTS_DIR / "few_shot_mined.yaml"
DEFAULT_REGLAS_DISCRIMINANTES = PROMPTS_DIR / "reglas_discriminantes.yaml"
COMPOSITES_CSV = TAXONOMY_DIR / "composites_index.csv"
COLISIONES_CSV = TAXONOMY_DIR / "colisiones_keyword.csv"


@dataclass(frozen=True)
class FewShotExample:
    id: str
    sector: str | None
    subsector: str | None
    tags: tuple[str, ...]
    proyecto: str
    respuesta: dict[str, Any]
    score: int = 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def load_few_shot_bank(path: str | None = None) -> list[FewShotExample]:
    if path:
        paths = [Path(path)]
    else:
        paths = [DEFAULT_FEW_SHOT, DEFAULT_FEW_SHOT_MINED]
    examples: list[FewShotExample] = []
    seen_ids: set[str] = set()
    for bank_path in paths:
        if not bank_path.exists():
            continue
        with bank_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        for item in raw.get("examples") or []:
            ex_id = str(item.get("id", ""))
            if ex_id in seen_ids:
                continue
            seen_ids.add(ex_id)
            examples.append(
                FewShotExample(
                    id=ex_id,
                    sector=item.get("sector"),
                    subsector=item.get("subsector"),
                    tags=tuple(item.get("tags") or ()),
                    proyecto=str(item.get("proyecto") or "").strip(),
                    respuesta=dict(item.get("respuesta") or {}),
                )
            )
    return examples


def _match_score(example: FewShotExample, sector: str, subsector: str) -> int:
    sec = normalize_key(sector)
    sub = normalize_key(subsector)
    ex_sec = normalize_key(example.sector) if example.sector else ""
    ex_sub = normalize_key(example.subsector) if example.subsector else ""
    if ex_sub and ex_sub == sub:
        return 100
    if ex_sec and ex_sec == sec:
        return 50
    if not ex_sec and not ex_sub:
        return 10
    return 0


def select_few_shot_examples(
    sector: str,
    subsector: str,
    *,
    bank: list[FewShotExample] | None = None,
    max_examples: int = 2,
    few_shot_path: Path | None = None,
) -> list[dict[str, Any]]:
    examples = bank or load_few_shot_bank(str(few_shot_path) if few_shot_path else None)
    scored = [
        ( _match_score(ex, sector, subsector), ex)
        for ex in examples
    ]
    scored.sort(key=lambda x: (-x[0], x[1].id))
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for score, ex in scored:
        if score <= 0 and selected:
            break
        if ex.id in seen_ids:
            continue
        if score <= 0 and not selected:
            # al menos un ejemplo global si no hay match
            pass
        elif score <= 0:
            continue
        seen_ids.add(ex.id)
        selected.append(
            {
                "id": ex.id,
                "proyecto": ex.proyecto,
                "respuesta_esperada": ex.respuesta,
            }
        )
        if len(selected) >= max_examples:
            break
    # Garantizar al menos 1 ejemplo global si hay pocos matches
    if len(selected) < max_examples:
        for ex in examples:
            if ex.id in seen_ids:
                continue
            if not ex.sector and not ex.subsector:
                selected.append(
                    {
                        "id": ex.id,
                        "proyecto": ex.proyecto,
                        "respuesta_esperada": ex.respuesta,
                    }
                )
                seen_ids.add(ex.id)
                if len(selected) >= max_examples:
                    break
    return selected


@lru_cache(maxsize=1)
def _colisiones_rows() -> list[dict[str, str]]:
    return _read_csv(COLISIONES_CSV)


@lru_cache(maxsize=1)
def _composites_rows() -> list[dict[str, str]]:
    return _read_csv(COMPOSITES_CSV)


def confusion_pairs_for_subsector(
    subsector: str,
    *,
    max_pairs: int = 5,
) -> list[dict[str, str]]:
    sub_norm = normalize_key(subsector)
    pairs: list[dict[str, str]] = []
    for row in _colisiones_rows():
        row_sub = normalize_key(row.get("subsector"))
        if row_sub != sub_norm:
            continue
        pairs.append(
            {
                "tipo_a": row.get("tipo_a", ""),
                "tipo_b": row.get("tipo_b", ""),
                "keywords_compartidas": row.get("keywords_compartidas", ""),
                "nota": (
                    "Estos tipos comparten keywords; distingue por definicion y actividad principal."
                ),
            }
        )
        if len(pairs) >= max_pairs:
            break
    return pairs


def composite_relations_for_subsector(
    sector: str,
    subsector: str,
    *,
    max_relations: int = 4,
) -> list[dict[str, str]]:
    sec_norm = normalize_key(sector)
    sub_norm = normalize_key(subsector)
    relations: list[dict[str, str]] = []
    for row in _composites_rows():
        if normalize_key(row.get("sector")) != sec_norm:
            continue
        if normalize_key(row.get("subsector")) != sub_norm:
            continue
        relations.append(
            {
                "tipo_compuesto": row.get("tipo_compuesto", ""),
                "tipo_id": row.get("tipo_id", ""),
                "partes_and": row.get("partes_and", ""),
                "subtipos": row.get("subtipos", ""),
                "nota": "Usar compuesto solo si TODAS las partes_and están en el texto; si no, subtipo.",
            }
        )
        if len(relations) >= max_relations:
            break
    return relations


@lru_cache(maxsize=1)
def _reglas_discriminantes() -> list[dict[str, Any]]:
    path = DEFAULT_REGLAS_DISCRIMINANTES
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return list(raw.get("subsectores") or [])


def guia_discriminante_for_subsector(sector: str, subsector: str) -> dict[str, Any] | None:
    """Guía curada de desambiguación para un subsector (jerarquía + reglas por par).

    Captura confusiones SEMÁNTICAS (validadas por experto) que no surgen de
    keywords compartidas, por lo que complementan `pares_confusos`.
    """
    sec_res, sub_res = resolve_sector_subsector(sector, subsector)
    sec = normalize_key(sec_res)
    sub = normalize_key(sub_res)
    for row in _reglas_discriminantes():
        if normalize_key(resolve_sector_subsector(row.get("sector"), row.get("subsector"))[1]) != sub:
            continue
        if normalize_key(resolve_sector_subsector(row.get("sector"), row.get("subsector"))[0]) != sec:
            continue
        guia: dict[str, Any] = {}
        if row.get("procedimiento"):
            guia["procedimiento"] = str(row["procedimiento"]).strip()
        reglas = [
            {"tipos": r.get("pares") or [], "regla": str(r.get("regla") or "").strip()}
            for r in (row.get("reglas") or [])
        ]
        if reglas:
            guia["reglas_por_par"] = reglas
        return guia or None
    return None


def build_dynamic_context(
    sector: str,
    subsector: str,
    *,
    max_few_shot: int = 2,
    max_confusion_pairs: int = 5,
    max_composite_relations: int = 4,
    few_shot_path: Path | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    guia = guia_discriminante_for_subsector(sector, subsector)
    if guia:
        context["guia_discriminante"] = guia
    pairs = confusion_pairs_for_subsector(subsector, max_pairs=max_confusion_pairs)
    if pairs:
        context["pares_confusos"] = pairs
    composites = composite_relations_for_subsector(
        sector, subsector, max_relations=max_composite_relations
    )
    if composites:
        context["relaciones_compuestas"] = composites
    examples = select_few_shot_examples(
        sector,
        subsector,
        max_examples=max_few_shot,
        few_shot_path=few_shot_path,
    )
    if examples:
        context["ejemplos_referencia"] = examples
    return context
