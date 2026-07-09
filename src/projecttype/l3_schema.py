"""Esquema Pydantic para prompts y respuestas L3."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class DescartadoModel(BaseModel):
    tipo_id: str
    motivo: str = ""


class L3ResponseModel(BaseModel):
    """Respuesta estructurada del LLM con chain-of-thought (Pydantic v2, no pydantic-ai)."""

    analisis: str = ""
    evidencia: list[str] = Field(default_factory=list)
    candidatos_descartados: list[DescartadoModel] = Field(default_factory=list)
    tipo_id: str | None = None
    confianza: float = Field(ge=0.0, le=1.0)
    razonamiento: str = ""

    @field_validator("tipo_id", mode="before")
    @classmethod
    def _normalize_tipo_id(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"null", "none"}:
            return None
        return text

    @field_validator("confianza", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: object) -> float:
        if value is None:
            return 0.0
        if isinstance(value, int | float | str):
            return float(value)
        return 0.0

    @field_validator("evidencia", mode="before")
    @classmethod
    def _coerce_evidencia(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list | tuple | set):
            return [str(v) for v in value if str(v).strip()]
        return []

    @field_validator("candidatos_descartados", mode="before")
    @classmethod
    def _coerce_descartados(cls, value: object) -> list[object]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        return []

    @classmethod
    def from_llm_dict(cls, raw: dict[str, Any]) -> L3ResponseModel:
        descartados = raw.get("candidatos_descartados") or []
        return cls.model_validate(
            {
                "analisis": raw.get("analisis") or raw.get("analysis") or "",
                "evidencia": raw.get("evidencia") or raw.get("evidence") or [],
                "candidatos_descartados": descartados,
                "tipo_id": raw.get("tipo_id"),
                "confianza": raw.get("confianza", raw.get("confidence", 0.0)),
                "razonamiento": raw.get("razonamiento", raw.get("reasoning") or ""),
            }
        )

    def to_reasoning_text(self) -> str:
        parts: list[str] = []
        if self.analisis:
            parts.append(f"Análisis: {self.analisis}")
        if self.evidencia:
            parts.append("Evidencia: " + " | ".join(self.evidencia[:4]))
        if self.candidatos_descartados:
            desc = "; ".join(
                f"{d.tipo_id.split('.')[-1]} ({d.motivo})"
                for d in self.candidatos_descartados[:3]
            )
            parts.append(f"Descartados: {desc}")
        if self.razonamiento:
            parts.append(f"Decisión: {self.razonamiento}")
        return "\n".join(parts) if parts else self.razonamiento


class L3PromptConfig(BaseModel):
    version: int = 2
    system_prompt: str
    reasoning_steps: list[dict[str, object]] = Field(default_factory=list)
    decision_rubric: dict[str, str] = Field(default_factory=dict)
    edge_cases: list[dict[str, object]] = Field(default_factory=list)
    response_schema: dict[str, str] = Field(default_factory=dict)
    settings: dict[str, int] = Field(default_factory=dict)

    @property
    def max_few_shot_examples(self) -> int:
        return int(self.settings.get("max_few_shot_examples", 2))

    @property
    def max_confusion_pairs(self) -> int:
        return int(self.settings.get("max_confusion_pairs", 5))

    @property
    def max_composite_relations(self) -> int:
        return int(self.settings.get("max_composite_relations", 4))
