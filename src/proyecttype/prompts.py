"""Construcción de prompts SOTA para clasificación L3 (LLM)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .composite import parse_tipo_components
from .l3_schema import L3PromptConfig
from .paths import PROJECT_ROOT
from .prompt_context import build_dynamic_context
from .taxonomy import TipoProyecto
from .text_utils import normalize_tipo_name
from .tipo_embedder import build_project_text

DEFAULT_L3_PROMPTS = PROJECT_ROOT / "data" / "prompts" / "l3.yaml"

_FALLBACK_SYSTEM = """\
Eres un clasificador experto de tipos de proyecto BIP/MDSF.
Responde con JSON: analisis, evidencia, candidatos_descartados, tipo_id, confianza, razonamiento."""


@lru_cache(maxsize=4)
def load_l3_prompt_config(path: str | Path | None = None) -> L3PromptConfig:
    prompt_path = Path(path) if path else DEFAULT_L3_PROMPTS
    if not prompt_path.exists():
        return L3PromptConfig(version=2, system_prompt=_FALLBACK_SYSTEM)
    with prompt_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return L3PromptConfig.model_validate(raw)


def get_l3_system_prompt(config: L3PromptConfig | None = None) -> str:
    cfg = config or load_l3_prompt_config()
    parts = [cfg.system_prompt.strip()]

    if cfg.reasoning_steps:
        parts.append("\n\nPasos de razonamiento:")
        for step in cfg.reasoning_steps:
            paso = str(step.get("paso") or step.get("instruction") or "")
            step_id = str(step.get("id") or "")
            label = step_id.replace("_", " ").title() if step_id else "Paso"
            if paso:
                parts.append(f"- {label}: {paso}")

    if cfg.decision_rubric:
        parts.append("\n\nRúbrica de decisión:")
        for key, text in cfg.decision_rubric.items():
            label = key.replace("_", " ").capitalize()
            parts.append(f"- {label}: {text.strip()}")

    if cfg.edge_cases:
        parts.append("\n\nCasos borde:")
        for case in cfg.edge_cases:
            titulo = str(case.get("titulo") or case.get("id") or "Caso")
            instruccion = str(case.get("instruccion") or "").strip()
            if instruccion:
                parts.append(f"- {titulo}: {instruccion}")

    if cfg.response_schema:
        parts.append("\n\nEsquema de respuesta JSON:")
        for field, desc in cfg.response_schema.items():
            parts.append(f"- {field}: {desc}")

    return "\n".join(parts)


def format_tipo_option(
    tipo: TipoProyecto,
    *,
    sibling_names: frozenset[str] | None = None,
    max_def_chars: int = 400,
) -> dict[str, Any]:
    definicion = (tipo.definicion or "").strip()
    if len(definicion) > max_def_chars:
        definicion = definicion[: max_def_chars - 3] + "..."
    keywords = ", ".join(list(tipo.keywords_fuertes[:6]) + list(tipo.keywords_debiles[:4]))
    siblings = sibling_names or frozenset()
    components = parse_tipo_components(tipo.nombre, siblings)
    option: dict[str, Any] = {
        "tipo_id": tipo.tipo_id,
        "nombre": tipo.nombre,
        "definicion": definicion,
        "keywords": keywords,
    }
    if tipo.excluye_si_contiene:
        option["excluye_si"] = list(tipo.excluye_si_contiene[:8])
    if components.is_composite:
        option["es_compuesto"] = True
        if components.and_parts:
            option["componentes_requeridas"] = list(components.and_parts)
        if components.or_groups:
            option["grupos_y_o"] = [list(group) for group in components.or_groups]
    return option


def _resolve_alternativas(
    alternativas_raw: str | None,
    tipos_by_id: dict[str, TipoProyecto],
) -> list[dict[str, str]]:
    if not alternativas_raw:
        return []
    result: list[dict[str, str]] = []
    for tipo_id in alternativas_raw.split("|"):
        tipo_id = tipo_id.strip()
        if not tipo_id:
            continue
        tipo = tipos_by_id.get(tipo_id)
        if tipo:
            result.append({"tipo_id": tipo.tipo_id, "nombre": tipo.nombre})
        else:
            result.append({"tipo_id": tipo_id, "nombre": ""})
    return result[:4]


def build_l3_user_prompt(
    *,
    sector: str,
    subsector: str,
    proyecto_text: str,
    tipos: list[TipoProyecto],
    l1_tipo_id: str | None = None,
    l1_tipo_nombre: str | None = None,
    l1_estado: str | None = None,
    l1_score: float | None = None,
    l1_margen: float | None = None,
    l1_alternativas: str | None = None,
    l2_tipo_id: str | None = None,
    l2_tipo_nombre: str | None = None,
    l2_estado: str | None = None,
    l2_similitud: float | None = None,
    l2_margen: float | None = None,
    codigo_bip: str | None = None,
    max_def_chars: int = 400,
    prompt_config: L3PromptConfig | None = None,
    include_dynamic_context: bool = True,
) -> str:
    cfg = prompt_config or load_l3_prompt_config()
    sibling_names = frozenset(normalize_tipo_name(t.nombre) for t in tipos)
    tipos_by_id = {t.tipo_id: t for t in tipos}
    opciones = [
        format_tipo_option(t, sibling_names=sibling_names, max_def_chars=max_def_chars)
        for t in tipos
    ]

    payload: dict[str, Any] = {
        "instruccion": (
            "Clasifica el proyecto siguiente. Usa el protocolo de razonamiento del system prompt. "
            "Responde SOLO con el JSON de salida."
        ),
        "sector": sector,
        "subsector": subsector,
        "proyecto": proyecto_text,
        "tipos_validos": opciones,
    }
    if codigo_bip:
        payload["codigo_bip"] = codigo_bip

    if include_dynamic_context:
        contexto = build_dynamic_context(
            sector,
            subsector,
            max_few_shot=cfg.max_few_shot_examples,
            max_confusion_pairs=cfg.max_confusion_pairs,
            max_composite_relations=cfg.max_composite_relations,
        )
        if contexto:
            payload["contexto_adicional"] = contexto

    sugerencias: dict[str, Any] = {}
    if l1_tipo_id or l1_tipo_nombre:
        sugerencias["l1"] = {
            "candidato": f"{l1_tipo_nombre} ({l1_tipo_id})",
            "estado": l1_estado,
        }
        if l1_score is not None:
            sugerencias["l1"]["score"] = round(l1_score, 2)
        if l1_margen is not None:
            sugerencias["l1"]["margen"] = round(l1_margen, 2)
        alts = _resolve_alternativas(l1_alternativas, tipos_by_id)
        if alts:
            sugerencias["l1"]["alternativas"] = alts
    if l2_tipo_id or l2_tipo_nombre:
        sugerencias["l2"] = {
            "candidato": f"{l2_tipo_nombre} ({l2_tipo_id})",
            "estado": l2_estado,
        }
        if l2_similitud is not None:
            sugerencias["l2"]["similitud"] = round(l2_similitud, 3)
        if l2_margen is not None:
            sugerencias["l2"]["margen"] = round(l2_margen, 3)
    if sugerencias:
        payload["sugerencias_previas"] = sugerencias

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_l3_messages(
    *,
    sector: str,
    subsector: str,
    proyecto_text: str,
    tipos: list[TipoProyecto],
    prompt_config: L3PromptConfig | None = None,
    **kwargs: Any,
) -> dict[str, str]:
    cfg = prompt_config or load_l3_prompt_config()
    return {
        "system": get_l3_system_prompt(cfg),
        "user": build_l3_user_prompt(
            sector=sector,
            subsector=subsector,
            proyecto_text=proyecto_text,
            tipos=tipos,
            prompt_config=cfg,
            **kwargs,
        ),
    }


def build_l3_project_text(
    *,
    nombre: str = "",
    descripcion: str = "",
    justificacion: str = "",
    descriptores: str = "",
    max_chars: int = 4000,
) -> str:
    return build_project_text(
        nombre=nombre,
        descripcion=descripcion,
        justificacion=justificacion,
        descriptores=descriptores,
        max_chars=max_chars,
    )
