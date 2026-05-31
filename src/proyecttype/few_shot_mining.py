"""Minería de ejemplos few-shot desde etiquetado manual vs L1/L2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from .evaluation import NivelMatch, clasificar_match, load_submuestra
from .paths import DEFAULT_SUBMUESTRA, DEFAULT_TAXONOMY
from .taxonomy import Taxonomia, TipoProyecto
from .text_utils import join_fields, normalize_key, normalize_text, normalize_tipo_name
from .tipo_embedder import build_project_text


@dataclass(frozen=True)
class MinedExample:
    id: str
    sector: str
    subsector: str
    tags: tuple[str, ...]
    proyecto: str
    respuesta: dict[str, Any]
    codigo_bip: str
    nivel_match_l1: str
    priority: int


def resolve_manual_tipo(
    tax: Taxonomia,
    *,
    sector: str | None,
    subsector: str | None,
    tipo_manual: str | None,
) -> TipoProyecto | None:
    if not tipo_manual:
        return None
    manual_norm = normalize_tipo_name(tipo_manual).upper()
    tipos = tax.tipos_para(sector, subsector)
    for tipo in tipos:
        if normalize_tipo_name(tipo.nombre).upper() == manual_norm:
            return tipo
    for tipo in tipos:
        tn = normalize_tipo_name(tipo.nombre).upper()
        if manual_norm in tn or tn in manual_norm:
            return tipo
    return None


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {c.strip(): c for c in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _project_text_from_row(row: dict[str, Any]) -> str:
    nombre = row.get("nombre") or row.get("NOMBRE") or ""
    descripcion = row.get("descripcion") or row.get("descripción") or row.get("_descripcion") or ""
    justificacion = (
        row.get("justificacion")
        or row.get("justificacion_proyecto")
        or row.get("_justificacion")
        or ""
    )
    descriptores = join_fields(
        row.get("descriptor_1"),
        row.get("descriptor_2"),
        row.get("descriptor_3"),
    )
    return build_project_text(
        nombre=str(nombre),
        descripcion=str(descripcion),
        justificacion=str(justificacion),
        descriptores=descriptores,
        max_chars=1200,
    )


def extract_evidencia(proyecto_text: str, tipo: TipoProyecto, *, max_items: int = 4) -> list[str]:
    text_norm = normalize_text(proyecto_text)
    if not text_norm:
        return []
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()

    def _try_add(raw: str, weight: int) -> None:
        kw_norm = normalize_text(raw)
        if len(kw_norm) < 4 or kw_norm in seen:
            return
        if kw_norm in text_norm:
            seen.add(kw_norm)
            # fragmento legible del texto original
            pattern = re.escape(kw_norm)
            match = re.search(pattern, text_norm, re.IGNORECASE)
            snippet = raw.strip()
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            candidates.append((weight, snippet))

    for kw in tipo.keywords_fuertes[:8]:
        _try_add(kw, 3)
    for kw in tipo.keywords_debiles[:6]:
        _try_add(kw, 1)
    _try_add(tipo.nombre, 4)

    if not candidates and proyecto_text:
        first = proyecto_text.strip().split(".")[0][:100]
        if first:
            candidates.append((0, first))

    candidates.sort(key=lambda x: -x[0])
    return [c[1] for c in candidates[:max_items]]


def build_descartados(
    *,
    manual_tipo_id: str,
    l1_tipo_id: str | None,
    l1_tipo_nombre: str | None,
    l2_tipo_id: str | None,
    l2_tipo_nombre: str | None,
    tipos_subsector: list[TipoProyecto],
) -> list[dict[str, str]]:
    descartados: list[dict[str, str]] = []
    if l1_tipo_id and l1_tipo_id != manual_tipo_id:
        descartados.append(
            {
                "tipo_id": l1_tipo_id,
                "motivo": f"L1 sugirió {l1_tipo_nombre or l1_tipo_id}; no coincide con la obra principal.",
            }
        )
    if l2_tipo_id and l2_tipo_id != manual_tipo_id and l2_tipo_id != l1_tipo_id:
        descartados.append(
            {
                "tipo_id": l2_tipo_id,
                "motivo": f"L2 sugirió {l2_tipo_nombre or l2_tipo_id}; descartado tras revisar definición.",
            }
        )
    if len(descartados) < 2:
        for tipo in tipos_subsector[:6]:
            if tipo.tipo_id == manual_tipo_id:
                continue
            if any(d["tipo_id"] == tipo.tipo_id for d in descartados):
                continue
            descartados.append(
                {
                    "tipo_id": tipo.tipo_id,
                    "motivo": f"Definición de {tipo.nombre} no describe la actividad principal.",
                }
            )
            if len(descartados) >= 2:
                break
    return descartados[:3]


def _priority_for_match(nivel: NivelMatch, l1_estado: str | None) -> int:
    if nivel == NivelMatch.DISCREPANCIA:
        return 100
    if nivel == NivelMatch.SIN_CLASIFICACION_L1:
        return 85 if l1_estado == "sin_match" else 75
    if nivel == NivelMatch.COINCIDENCIA_PARCIAL:
        return 40
    return 0


def _slug(text: str, max_len: int = 24) -> str:
    value = normalize_text(text).replace(" ", "_")
    return value[:max_len] or "caso"


def mine_few_shot_examples(
    resultados: pl.DataFrame,
    manual: pl.DataFrame,
    tax: Taxonomia,
    *,
    min_proyecto_chars: int = 120,
    max_per_subsector: int = 2,
    max_total: int = 50,
) -> list[MinedExample]:
    man = manual.with_columns(
        pl.col("codigo_bip").cast(pl.Utf8).str.strip_chars(),
    ).filter(pl.col("tipo_proyecto").is_not_null())

    man_columns = list(man.columns)
    justificacion_col = _pick_column(man_columns, ("justificación_proyecto", "justificacion_proyecto"))
    descripcion_col = _pick_column(man_columns, ("descripción", "descripcion"))

    man_select: list[str | pl.Expr] = [
        "codigo_bip",
        "nombre",
        "sector",
        "subsector",
        "tipo_proyecto",
    ]
    if justificacion_col:
        man_select.append(pl.col(justificacion_col).alias("_justificacion"))
    if descripcion_col:
        man_select.append(pl.col(descripcion_col).alias("_descripcion"))

    res = resultados.with_columns(
        pl.col("Codigo BIP").cast(pl.Utf8).str.strip_chars().alias("codigo_bip")
    )
    l1_cols = [
        c
        for c in (
            "codigo_bip",
            "l1_estado",
            "l1_tipo_id",
            "l1_tipo_nombre",
            "l2_tipo_id",
            "l2_tipo_nombre",
        )
        if c in res.columns or c == "codigo_bip"
    ]
    merged = man.select(man_select).join(res.select(l1_cols), on="codigo_bip", how="inner")

    candidates: list[MinedExample] = []
    for row in merged.iter_rows(named=True):
        tipo_manual = row.get("tipo_proyecto")
        l1_estado = row.get("l1_estado")
        l1_tipo = row.get("l1_tipo_nombre")
        nivel = clasificar_match(l1_tipo, tipo_manual, l1_estado=l1_estado)
        if nivel == NivelMatch.COINCIDENCIA_EXACTA:
            continue
        priority = _priority_for_match(nivel, l1_estado)
        if priority <= 0:
            continue

        sector = str(row.get("sector") or "")
        subsector = str(row.get("subsector") or "")
        tipo = resolve_manual_tipo(
            tax, sector=sector, subsector=subsector, tipo_manual=str(tipo_manual)
        )
        if tipo is None:
            continue

        proyecto = _project_text_from_row(row)
        if len(proyecto.strip()) < min_proyecto_chars:
            continue

        tipos_sub = tax.tipos_para(sector, subsector)
        evidencia = extract_evidencia(proyecto, tipo)
        descartados = build_descartados(
            manual_tipo_id=tipo.tipo_id,
            l1_tipo_id=row.get("l1_tipo_id"),
            l1_tipo_nombre=row.get("l1_tipo_nombre"),
            l2_tipo_id=row.get("l2_tipo_id"),
            l2_tipo_nombre=row.get("l2_tipo_nombre"),
            tipos_subsector=tipos_sub,
        )
        codigo = str(row.get("codigo_bip") or "")
        analisis = (
            f"Según el texto, la actividad principal corresponde a {tipo.nombre.lower()}"
            f" ({sector} / {subsector})."
        )
        razonamiento = (
            f"Etiqueta manual: {tipo_manual}. "
            f"Evidencia en nombre/descripción alinea con definición de {tipo.nombre}."
        )
        if nivel == NivelMatch.DISCREPANCIA:
            tag = "discrepancia_l1"
        elif nivel == NivelMatch.SIN_CLASIFICACION_L1:
            tag = "sin_clasificacion_l1"
        else:
            tag = "parcial_l1"

        candidates.append(
            MinedExample(
                id=f"mined_{codigo}",
                sector=sector,
                subsector=subsector,
                tags=("mined", tag, _slug(subsector)),
                proyecto=proyecto,
                respuesta={
                    "analisis": analisis,
                    "evidencia": evidencia,
                    "candidatos_descartados": descartados,
                    "tipo_id": tipo.tipo_id,
                    "confianza": 0.88,
                    "razonamiento": razonamiento,
                },
                codigo_bip=codigo,
                nivel_match_l1=nivel.value,
                priority=priority + min(len(proyecto) // 100, 10),
            )
        )

    candidates.sort(key=lambda c: (-c.priority, c.codigo_bip))

    by_nivel: dict[str, list[MinedExample]] = {}
    for cand in candidates:
        by_nivel.setdefault(cand.nivel_match_l1, []).append(cand)

    quotas = {
        NivelMatch.SIN_CLASIFICACION_L1.value: max(1, max_total // 4),
        NivelMatch.COINCIDENCIA_PARCIAL.value: max(1, max_total // 10),
        NivelMatch.DISCREPANCIA.value: max_total,
    }

    selected: list[MinedExample] = []
    per_subsector: dict[str, int] = {}
    seen_bip: set[str] = set()

    def _try_add(cand: MinedExample) -> bool:
        if cand.codigo_bip in seen_bip:
            return False
        key = normalize_key(cand.subsector)
        if per_subsector.get(key, 0) >= max_per_subsector:
            return False
        selected.append(cand)
        seen_bip.add(cand.codigo_bip)
        per_subsector[key] = per_subsector.get(key, 0) + 1
        return True

    for nivel in (
        NivelMatch.SIN_CLASIFICACION_L1.value,
        NivelMatch.COINCIDENCIA_PARCIAL.value,
        NivelMatch.DISCREPANCIA.value,
    ):
        quota = quotas.get(nivel, 0)
        taken = 0
        for cand in by_nivel.get(nivel, []):
            if len(selected) >= max_total or taken >= quota:
                break
            if _try_add(cand):
                taken += 1

    if len(selected) < max_total:
        for cand in candidates:
            if len(selected) >= max_total:
                break
            _try_add(cand)

    return selected


def examples_to_yaml_dict(examples: list[MinedExample]) -> dict[str, Any]:
    return {
        "version": 1,
        "source": "mined_from_submuestra",
        "examples": [
            {
                "id": ex.id,
                "sector": ex.sector,
                "subsector": ex.subsector,
                "tags": list(ex.tags),
                "codigo_bip": ex.codigo_bip,
                "nivel_match_l1": ex.nivel_match_l1,
                "proyecto": ex.proyecto,
                "respuesta": ex.respuesta,
            }
            for ex in examples
        ],
    }


def write_few_shot_yaml(examples: list[MinedExample], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = examples_to_yaml_dict(examples)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(payload, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return path


def merge_few_shot_banks(
    curated_path: Path,
    mined_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    """Fusiona bancos; curated gana en conflicto de id."""
    curated: dict[str, Any] = {"examples": []}
    mined: dict[str, Any] = {"examples": []}
    if curated_path.exists():
        with curated_path.open(encoding="utf-8") as fh:
            curated = yaml.safe_load(fh) or {"examples": []}
    if mined_path.exists():
        with mined_path.open(encoding="utf-8") as fh:
            mined = yaml.safe_load(fh) or {"examples": []}

    by_id: dict[str, dict] = {}
    for item in curated.get("examples") or []:
        by_id[str(item.get("id"))] = item
    n_mined = 0
    for item in mined.get("examples") or []:
        item_id = str(item.get("id"))
        if item_id not in by_id:
            by_id[item_id] = item
            n_mined += 1

    merged = {
        "version": curated.get("version", 1),
        "examples": list(by_id.values()),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        yaml.dump(merged, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return len(by_id), n_mined


def mine_from_files(
    *,
    resultados_path: Path,
    submuestra_path: Path = DEFAULT_SUBMUESTRA,
    taxonomy_path: Path = DEFAULT_TAXONOMY,
    max_per_subsector: int = 2,
    max_total: int = 50,
) -> list[MinedExample]:
    tax = Taxonomia.from_yaml(taxonomy_path)
    manual = load_submuestra(submuestra_path)
    resultados = pl.read_csv(resultados_path)
    return mine_few_shot_examples(
        resultados,
        manual,
        tax,
        max_per_subsector=max_per_subsector,
        max_total=max_total,
    )
