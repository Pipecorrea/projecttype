"""Metadatos de inferencia SC-13 para enr_tipo_proyecto (PT-9)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .paths import DEFAULT_FEW_SHOT_MINED, DEFAULT_L3_PROMPTS, DEFAULT_TAXONOMY, PROMPTS_DIR

EVIDENCIA_MAX_CHARS = 500
_PROMPT_FILES = (
    DEFAULT_L3_PROMPTS,
    PROMPTS_DIR / "reglas_discriminantes.yaml",
    PROMPTS_DIR / "few_shot_examples.yaml",
    DEFAULT_FEW_SHOT_MINED,
)


def short_hash(content: bytes) -> str:
    """SHA-256 truncado a 12 hex (convención ecosistema SC-13)."""
    return hashlib.sha256(content).hexdigest()[:12]


def prompt_version(*, prompts_dir: Path | None = None) -> str:
    """Hash corto del bundle de prompts L3 (runtime, no hardcodeado)."""
    base = prompts_dir or PROMPTS_DIR
    parts: list[bytes] = []
    for rel in _PROMPT_FILES:
        path = rel if rel.is_absolute() else base / rel.name if rel.parent == PROMPTS_DIR else rel
        if not path.is_file():
            path = base / rel.name if (base / rel.name).is_file() else rel
        if path.is_file():
            parts.append(path.read_bytes())
    if not parts:
        return short_hash(b"")
    return short_hash(b"".join(parts))


def taxonomy_hash(*, taxonomy_path: Path | None = None) -> str:
    """Hash corto de la taxonomía versionada."""
    path = taxonomy_path or DEFAULT_TAXONOMY
    return short_hash(path.read_bytes())


def truncate_evidencia(text: str | None, *, max_chars: int = EVIDENCIA_MAX_CHARS) -> str:
    """Recorta evidencia al límite del contrato SC-13."""
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1] + "…"


def _nivel_asignacion(nivel_final: int | None, estado_final: str | None) -> str:
    if estado_final in ("sin_match", "ambiguo", "sin_taxonomia") or nivel_final is None:
        return "residual"
    mapping = {1: "L1", 2: "L2", 3: "L3"}
    return mapping.get(int(nivel_final), "residual")


def _evidencia_l1(row: dict[str, Any]) -> str:
    evidencia = str(row.get("l1_evidencia") or "").strip()
    score = row.get("l1_score")
    if evidencia and score is not None:
        return truncate_evidencia(f"{evidencia}; score={score:.2f}")
    if evidencia:
        return truncate_evidencia(evidencia)
    if score is not None:
        return truncate_evidencia(f"score={score:.2f}")
    return ""


def _evidencia_l2(row: dict[str, Any]) -> str:
    vecino = row.get("l2_tipo_nombre") or row.get("l2_tipo_id") or "?"
    sim = row.get("l2_similitud")
    if sim is not None:
        return truncate_evidencia(f"vecino={vecino}; sim={float(sim):.3f}")
    return truncate_evidencia(f"vecino={vecino}")


def _evidencia_l3(row: dict[str, Any]) -> str:
    base = truncate_evidencia(str(row.get("l3_razonamiento") or ""))
    secs = row.get("l3_tipos_secundarios_nombres")
    if secs:
        suffix = f"; secundarios={secs}"
        return truncate_evidencia(f"{base}{suffix}" if base else f"secundarios={secs}")
    return base


def _evidencia_residual(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("l1_estado", "l2_estado", "l3_estado"):
        val = row.get(key)
        if val:
            parts.append(f"{key}={val}")
    return truncate_evidencia("; ".join(parts) or "sin clasificación")


def evidencia_resumen_for_row(row: dict[str, Any], *, nivel: str) -> str:
    """Resumen de evidencia según el nivel que asignó."""
    if nivel == "L1":
        return _evidencia_l1(row)
    if nivel == "L2":
        return _evidencia_l2(row)
    if nivel == "L3":
        return _evidencia_l3(row)
    return _evidencia_residual(row)


def confianza_for_row(row: dict[str, Any], *, nivel: str) -> float | None:
    """Score del nivel ganador; NULL para residual."""
    if nivel == "L1":
        val = row.get("l1_score")
        return float(val) if val is not None else None
    if nivel == "L2":
        val = row.get("l2_similitud")
        return float(val) if val is not None else None
    if nivel == "L3":
        val = row.get("l3_confianza")
        return float(val) if val is not None else None
    return None


def modelo_for_row(row: dict[str, Any], *, nivel: str, default_modelo: str = "n/a") -> str:
    """Id del modelo L3; ``n/a`` para L1/L2/residual."""
    if nivel == "L3":
        return str(row.get("_modelo_l3") or default_modelo)
    return "n/a"


def inference_fields_for_row(
    row: dict[str, Any],
    *,
    prompt_ver: str,
    tax_hash: str,
    default_modelo: str = "n/a",
) -> dict[str, Any]:
    """Proyecta metadatos SC-13 para una fila de la cascada."""
    nivel = _nivel_asignacion(row.get("nivel_final"), row.get("estado_final"))
    return {
        "nivel_asignacion": nivel,
        "confianza": confianza_for_row(row, nivel=nivel),
        "evidencia_resumen": evidencia_resumen_for_row(row, nivel=nivel),
        "modelo": modelo_for_row(row, nivel=nivel, default_modelo=default_modelo),
        "prompt_version": prompt_ver,
        "taxonomy_hash": tax_hash,
    }
