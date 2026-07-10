"""Clasificador Nivel 3: LLM con lista cerrada de tipos por subsector."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .aliases import resolve_sector_subsector
from .l3_schema import L3ResponseModel
from .llm_client import JSONParseError, LLMClient, LLMConfig, create_llm_client
from .progress import ProgressCallback
from .prompts import (
    build_l3_messages,
    build_l3_project_text,
    load_l3_prompt_config,
)
from .scorer import EstadoClasificacion, ProyectoTexto, ResultadoClasificacion
from .taxonomy import Taxonomia, TipoProyecto
from .text_utils import join_fields


@dataclass(frozen=True)
class L3Config:
    min_confidence: float = 0.75
    max_project_chars: int = 4000
    max_tipo_def_chars: int = 400
    llm: LLMConfig | None = None
    mock: bool = False
    prompts_path: Path | None = None


@dataclass
class L3TipoSecundario:
    tipo_id: str
    confianza: float
    motivo: str = ""


@dataclass
class L3Response:
    tipo_id: str | None
    confianza: float
    razonamiento: str
    tipos_secundarios: list[L3TipoSecundario] = field(default_factory=list)
    multi_tipo: bool = False
    validation_error: str | None = None


def parse_l3_response(raw: dict[str, Any]) -> L3Response:
    try:
        model = L3ResponseModel.from_llm_dict(raw)
        secundarios = [
            L3TipoSecundario(
                tipo_id=item.tipo_id,
                confianza=item.confianza,
                motivo=item.motivo,
            )
            for item in model.tipos_secundarios
        ]
        return L3Response(
            tipo_id=model.tipo_id,
            confianza=model.confianza,
            razonamiento=model.to_reasoning_text(),
            tipos_secundarios=secundarios,
            multi_tipo=model.multi_tipo or bool(secundarios),
        )
    except ValidationError as exc:
        return L3Response(
            tipo_id=None,
            confianza=0.0,
            razonamiento=str(raw.get("razonamiento") or raw.get("reasoning") or ""),
            validation_error=str(exc),
        )


def _validar_secundarios(
    response: L3Response,
    tipos_by_id: dict[str, TipoProyecto],
    principal_id: str | None,
) -> list[tuple[TipoProyecto, L3TipoSecundario]]:
    valid: list[tuple[TipoProyecto, L3TipoSecundario]] = []
    for sec in response.tipos_secundarios:
        if not sec.tipo_id or sec.tipo_id == principal_id:
            continue
        tipo = tipos_by_id.get(sec.tipo_id)
        if tipo is None:
            continue
        valid.append((tipo, sec))
        if len(valid) >= 2:
            break
    return valid


def _aplicar_secundarios(
    base: ResultadoClasificacion,
    valid_secs: list[tuple[TipoProyecto, L3TipoSecundario]],
    *,
    multi_tipo: bool,
) -> None:
    if not valid_secs:
        return
    base.tipos_secundarios_ids = [tipo.tipo_id for tipo, _ in valid_secs]
    base.tipos_secundarios_nombres = [tipo.nombre for tipo, _ in valid_secs]
    base.multi_tipo = multi_tipo or bool(valid_secs)


def _result_from_l3(
    response: L3Response,
    tipos_by_id: dict[str, TipoProyecto],
    config: L3Config,
    sector_res: str,
    subsector_res: str,
) -> tuple[ResultadoClasificacion, str]:
    base = ResultadoClasificacion(
        estado=EstadoClasificacion.SIN_MATCH,
        sector_resuelto=sector_res,
        subsector_resuelto=subsector_res,
        nivel=3,
        score=response.confianza,
    )
    razonamiento = response.razonamiento
    if response.validation_error:
        razonamiento = f"{razonamiento} [validación: {response.validation_error}]".strip()

    valid_secs = _validar_secundarios(response, tipos_by_id, response.tipo_id)
    _aplicar_secundarios(base, valid_secs, multi_tipo=response.multi_tipo)

    if not response.tipo_id or response.confianza < config.min_confidence:
        if response.tipo_id and response.confianza >= config.min_confidence * 0.6:
            tipo = tipos_by_id.get(response.tipo_id)
            if tipo:
                base.estado = EstadoClasificacion.AMBIGUO
                base.tipo_id = tipo.tipo_id
                base.tipo_nombre = tipo.nombre
        return base, razonamiento

    tipo = tipos_by_id.get(response.tipo_id)
    if not tipo:
        return base, razonamiento

    base.estado = EstadoClasificacion.ASIGNADO
    base.tipo_id = tipo.tipo_id
    base.tipo_nombre = tipo.nombre
    base.score = response.confianza
    return base, razonamiento


class ClassifierL3:
    def __init__(
        self,
        taxonomia: Taxonomia,
        client: LLMClient,
        config: L3Config | None = None,
    ) -> None:
        self.taxonomia = taxonomia
        self.client = client
        self.config = config or L3Config()
        self._prompt_config = load_l3_prompt_config(self.config.prompts_path)

    @classmethod
    def from_yaml(
        cls,
        taxonomy_path: str | Path,
        *,
        config: L3Config | None = None,
        mock: bool = False,
    ) -> ClassifierL3:
        cfg = config or L3Config(mock=mock)
        if mock:
            cfg = L3Config(
                min_confidence=cfg.min_confidence,
                max_project_chars=cfg.max_project_chars,
                max_tipo_def_chars=cfg.max_tipo_def_chars,
                llm=cfg.llm,
                mock=True,
                prompts_path=cfg.prompts_path,
            )
        tax = Taxonomia.from_yaml(taxonomy_path)
        client = create_llm_client(cfg.llm, mock=cfg.mock)
        return cls(tax, client, cfg)

    def build_prompt_messages(
        self,
        *,
        sector: str | None,
        subsector: str | None,
        nombre: str | None = None,
        descripcion: str | None = None,
        justificacion: str | None = None,
        descriptor_1: str | None = None,
        descriptor_2: str | None = None,
        descriptor_3: str | None = None,
        proyecto: ProyectoTexto | None = None,
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
        cached_content: str | None = None,
    ) -> dict[str, str]:
        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        tipos = self.taxonomia.tipos_para(sector, subsector)
        if proyecto is None:
            proyecto = ProyectoTexto(
                nombre=nombre or "",
                descripcion=descripcion or "",
                justificacion=justificacion or "",
                descriptores=join_fields(descriptor_1, descriptor_2, descriptor_3),
            )
        proyecto_text = build_l3_project_text(
            nombre=proyecto.nombre,
            descripcion=proyecto.descripcion,
            justificacion=proyecto.justificacion,
            descriptores=proyecto.descriptores,
            max_chars=self.config.max_project_chars,
        )
        return build_l3_messages(
            sector=sector_res,
            subsector=subsector_res,
            proyecto_text=proyecto_text,
            tipos=tipos,
            prompt_config=self._prompt_config,
            l1_tipo_id=l1_tipo_id,
            l1_tipo_nombre=l1_tipo_nombre,
            l1_estado=l1_estado,
            l1_score=l1_score,
            l1_margen=l1_margen,
            l1_alternativas=l1_alternativas,
            l2_tipo_id=l2_tipo_id,
            l2_tipo_nombre=l2_tipo_nombre,
            l2_estado=l2_estado,
            l2_similitud=l2_similitud,
            l2_margen=l2_margen,
            codigo_bip=codigo_bip,
            max_def_chars=self.config.max_tipo_def_chars,
            dynamic_only=cached_content is not None,
        )

    def classify_row(
        self,
        *,
        sector: str | None,
        subsector: str | None,
        nombre: str | None = None,
        descripcion: str | None = None,
        justificacion: str | None = None,
        descriptor_1: str | None = None,
        descriptor_2: str | None = None,
        descriptor_3: str | None = None,
        proyecto: ProyectoTexto | None = None,
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
        cached_content: str | None = None,
    ) -> tuple[ResultadoClasificacion, str]:
        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        tipos = self.taxonomia.tipos_para(sector, subsector)
        tipos_by_id = {t.tipo_id: t for t in tipos}

        if not tipos:
            return (
                ResultadoClasificacion(
                    estado=EstadoClasificacion.SIN_TAXONOMIA,
                    sector_resuelto=sector_res,
                    subsector_resuelto=subsector_res,
                    nivel=3,
                ),
                "",
            )

        messages = self.build_prompt_messages(
            sector=sector,
            subsector=subsector,
            nombre=nombre,
            descripcion=descripcion,
            justificacion=justificacion,
            descriptor_1=descriptor_1,
            descriptor_2=descriptor_2,
            descriptor_3=descriptor_3,
            proyecto=proyecto,
            l1_tipo_id=l1_tipo_id,
            l1_tipo_nombre=l1_tipo_nombre,
            l1_estado=l1_estado,
            l1_score=l1_score,
            l1_margen=l1_margen,
            l1_alternativas=l1_alternativas,
            l2_tipo_id=l2_tipo_id,
            l2_tipo_nombre=l2_tipo_nombre,
            l2_estado=l2_estado,
            l2_similitud=l2_similitud,
            l2_margen=l2_margen,
            codigo_bip=codigo_bip,
            cached_content=cached_content,
        )

        try:
            raw = self.client.complete_json(
                system=messages["system"],
                user=messages["user"],
                cached_content=cached_content,
            )
        except (JSONParseError, RuntimeError, TimeoutError, OSError) as exc:
            err = ResultadoClasificacion(
                estado=EstadoClasificacion.SIN_MATCH,
                sector_resuelto=sector_res,
                subsector_resuelto=subsector_res,
                nivel=3,
            )
            return err, f"Error LLM: {exc}"

        response = parse_l3_response(raw)
        return _result_from_l3(response, tipos_by_id, self.config, sector_res, subsector_res)

    def classify_rows_batch(
        self,
        rows: list[dict[str, Any]],
        *,
        sector: str | None,
        subsector: str | None,
        on_progress: ProgressCallback | None = None,
        progress_offset: int = 0,
        progress_total: int | None = None,
    ) -> list[tuple[ResultadoClasificacion, str]]:
        total = progress_total if progress_total is not None else progress_offset + len(rows)
        results: list[tuple[ResultadoClasificacion, str]] = []
        for i, row in enumerate(rows):
            codigo = row.get("codigo_bip") or row.get("Codigo BIP")
            result = self.classify_row(
                sector=sector,
                subsector=subsector,
                nombre=row.get("nombre") or row.get("NOMBRE"),
                descripcion=row.get("descripcion") or row.get("descripción"),
                justificacion=row.get("justificacion") or row.get("justificacion_proyecto"),
                descriptor_1=row.get("descriptor_1"),
                descriptor_2=row.get("descriptor_2"),
                descriptor_3=row.get("descriptor_3"),
                l1_tipo_id=row.get("l1_tipo_id"),
                l1_tipo_nombre=row.get("l1_tipo_nombre"),
                l1_estado=row.get("l1_estado"),
                l1_score=_float_or_none(row.get("l1_score")),
                l1_margen=_float_or_none(row.get("l1_margen")),
                l1_alternativas=row.get("l1_alternativas"),
                l2_tipo_id=row.get("l2_tipo_id"),
                l2_tipo_nombre=row.get("l2_tipo_nombre"),
                l2_estado=row.get("l2_estado"),
                l2_similitud=_float_or_none(row.get("l2_similitud")),
                l2_margen=_float_or_none(row.get("l2_margen")),
                codigo_bip=str(codigo) if codigo else None,
            )
            results.append(result)
            if on_progress:
                on_progress(progress_offset + i + 1, total, str(codigo) if codigo else None)
        return results


def _float_or_none(value: object) -> float | None:
    if value is None or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
